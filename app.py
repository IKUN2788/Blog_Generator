"""
文章生成器 - Flask Web 应用
提供文章生成、管理和查看功能的 Web 界面
"""
import webbrowser
from flask import Flask, render_template, request, jsonify
from core.generator import ArticleGenerator
from utils.config import ConfigManager

app = Flask(__name__)

# 初始化配置管理器和文章生成器
config_manager = ConfigManager()
api_key = config_manager.get("api_key")

try:
    generator = ArticleGenerator(api_key=api_key)
except ValueError:
    print("警告: 未找到 API Key，请在设置中配置")
    generator = ArticleGenerator(api_key="dummy_key_waiting_for_config")

# 从配置加载并发线程数
saved_workers = config_manager.get("max_workers", 3)
try:
    generator.set_max_workers(int(saved_workers))
except Exception:
    pass

# 全局状态（生产环境建议使用 Redis）
generation_status = {
    'is_running': False,
    'current': 0,
    'total': 0,
    'success': 0,
    'errors': 0,
    'rate_remaining': 100,
    'elapsed_time': 0,
    'avg_time': 0,
    'logs': []
}


def progress_callback(current, total, success, errors, rate_remaining):
    """进度回调函数"""
    global generation_status
    generation_status.update({
        'is_running': True,
        'current': current,
        'total': total,
        'success': success,
        'errors': errors,
        'rate_remaining': rate_remaining
    })
    gen_status = generator.get_status()
    generation_status['elapsed_time'] = gen_status.get('elapsed_time', 0)
    generation_status['avg_time'] = gen_status.get('avg_time', 0)


def completion_callback(total, success, errors):
    """完成回调函数"""
    global generation_status
    generation_status.update({
        'is_running': False,
        'current': total,
        'total': total,
        'success': success,
        'errors': errors
    })
    gen_status = generator.get_status()
    generation_status['rate_remaining'] = gen_status.get('rate_remaining', generation_status['rate_remaining'])
    generation_status['elapsed_time'] = gen_status.get('elapsed_time', 0)
    generation_status['avg_time'] = gen_status.get('avg_time', 0)
    generation_status['logs'].append(f"批次完成: {success} 成功, {errors} 失败")


# ==================== 路由定义 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """获取当前生成状态"""
    global generation_status
    gen_status = generator.get_status()
    generation_status.update({
        'is_running': gen_status.get('is_running', generation_status['is_running']),
        'current': gen_status.get('current', generation_status['current']),
        'total': gen_status.get('total', generation_status['total']),
        'success': gen_status.get('success', generation_status['success']),
        'errors': gen_status.get('errors', generation_status['errors']),
        'rate_remaining': gen_status.get('rate_remaining', generation_status['rate_remaining']),
        'elapsed_time': gen_status.get('elapsed_time', generation_status['elapsed_time']),
        'avg_time': gen_status.get('avg_time', generation_status['avg_time'])
    })
    return jsonify(generation_status)


@app.route('/api/generate', methods=['POST'])
def start_generation():
    """开始生成文章"""
    data = request.json
    tag_seed = data.get('tag_seed', '')
    count = int(data.get('count', 1))
    length = data.get('length', '6000')
    sequential = bool(data.get('sequential', False))
    
    if not tag_seed:
        return jsonify({'error': '主题不能为空'}), 400
        
    if generator.is_running:
        return jsonify({'error': '生成任务正在进行中'}), 400
    
    # 重置状态
    global generation_status
    generation_status = {
        'is_running': True,
        'current': 0,
        'total': count,
        'success': 0,
        'errors': 0,
        'rate_remaining': 100,
        'elapsed_time': 0,
        'avg_time': 0,
        'logs': [f"开始生成: '{tag_seed}', 数量: {count}"]
    }
    
    # 后台启动生成任务
    generator.generate_articles(
        tag_seed=tag_seed,
        count=count,
        length=length,
        progress_callback=progress_callback,
        completion_callback=completion_callback,
        sequential=sequential
    )
    
    return jsonify({'success': True, 'message': '生成任务已启动'})


@app.route('/api/stop', methods=['POST'])
def stop_generation():
    """停止生成"""
    generator.stop_generation()
    return jsonify({'success': True, 'message': '正在停止生成...'})


@app.route('/api/articles')
def get_articles():
    """获取文章列表（分页 + 多条件搜索）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    filter_read = request.args.get('filter', 'all', type=str)
    search_title = request.args.get('search_title', '', type=str)
    search_tags = request.args.get('search_tags', '', type=str)
    filter_status = request.args.get('filter_status', 'all', type=str)
    sort_field = request.args.get('sort_field', 'created_at', type=str)
    sort_order = request.args.get('sort_order', 'desc', type=str)
    return jsonify(generator.get_articles_paginated(page, per_page, filter_read, search_title, search_tags, filter_status, sort_field, sort_order))


@app.route('/api/article/<int:article_id>/toggle-read', methods=['POST'])
def toggle_read(article_id):
    """切换文章已读状态"""
    success = generator.toggle_read_status(article_id)
    return jsonify({'success': success})


@app.route('/api/article/<int:article_id>')
def get_article(article_id):
    """获取单篇文章详情"""
    article = generator.get_article(article_id)
    if article:
        return jsonify(article)
    return jsonify({'error': '文章不存在'}), 404


@app.route('/api/article/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    """删除指定文章"""
    generator.delete_article(article_id)
    return jsonify({'success': True})


@app.route('/api/articles/clear', methods=['POST'])
def clear_database():
    """清空数据库"""
    generator.clear_database()
    return jsonify({'success': True})


@app.route('/api/articles/correction', methods=['POST'])
def correction():
    """执行数据修正"""
    stats = generator.perform_correction()
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/articles/reorder', methods=['POST'])
def reorder_ids():
    """重新排序文章 ID"""
    stats = generator.reorder_ids()
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """获取或更新设置"""
    if request.method == 'POST':
        data = request.json
        api_key = data.get('api_key')
        max_workers = data.get('max_workers')
        
        if api_key:
            config_manager.set('api_key', api_key)
            from core.api_client import APIClient
            generator.client = APIClient(api_key=api_key)
            
        if max_workers is not None:
            try:
                workers = int(max_workers)
                if 1 <= workers <= 10:
                    config_manager.set('max_workers', workers)
                    generator.set_max_workers(workers)
            except Exception as e:
                print(f"更新并发数失败: {e}")
                
        return jsonify({'success': True})
    else:
        return jsonify({
            'api_key': config_manager.get('api_key', ''),
            'max_workers': config_manager.get('max_workers', 3)
        })


@app.route('/api/tags')
def get_tags():
    """获取预设标签分类"""
    return jsonify(generator.get_tag_categories())


if __name__ == '__main__':
    webbrowser.open('http://127.0.0.1:5000')
    app.run(debug=True, use_reloader=False)
