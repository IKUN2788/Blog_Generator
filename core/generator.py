"""
文章生成器 - 协调数据库和 API 客户端
"""
import threading
import time
import random
import json
import os
from typing import Callable, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.database import Database
from core.api_client import APIClient


class ArticleGenerator:
    """文章生成器"""
    
    def __init__(self, db_path: str = "data/articles.db", 
                 api_key: Optional[str] = None,
                 rate_limit: int = 100,
                 tags_file: str = "data/tags.json",
                 max_workers: int = 3):
        """初始化生成器"""
        self.database = Database(db_path)
        self.client = APIClient(api_key=api_key, rate_limit=rate_limit)
        self.is_running = False
        self.current_article = 0
        self.total_articles = 0
        self.success_count = 0
        self.error_count = 0
        self.current_seed = ""
        self.tags_data = self._load_tags(tags_file)
        self.max_workers = max_workers
        self.executor = None
        self.batch_start_time = 0
        self.batch_end_time = 0

    def set_max_workers(self, workers: int):
        """设置最大并发数"""
        self.max_workers = workers

    def _load_tags(self, tags_file: str) -> dict:
        """加载标签数据"""
        if os.path.exists(tags_file):
            try:
                with open(tags_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载标签失败: {e}")
        return {}

    def get_tag_categories(self) -> List[str]:
        """获取标签分类列表"""
        return list(self.tags_data.keys())
    
    def generate_articles(self, tag_seed: str, count: int, length: str = "6000",
                         progress_callback: Optional[Callable] = None,
                         completion_callback: Optional[Callable] = None,
                         sequential: bool = False):
        """生成多篇文章（count=-1 表示无限生成）"""
        self.is_running = True
        self.current_seed = tag_seed
        self.total_articles = count
        self.current_article = 0
        self.success_count = 0
        self.error_count = 0
        self.batch_start_time = time.time()
        self.batch_end_time = 0
        
        # 无限生成模式
        infinite_mode = (count == -1)
        
        def process_single_article(index: int):
            """处理单篇文章生成"""
            try:
                if not self.is_running:
                    return
                
                # 确定当前文章的种子
                current_seed = tag_seed
                
                if tag_seed in self.tags_data:
                    keywords_list = self.tags_data[tag_seed]
                    if keywords_list:
                        if sequential:
                            # 顺序生成：分类 + 当前关键词
                            idx = (index - 1) % len(keywords_list)
                            keyword = keywords_list[idx]
                            current_seed = f"{tag_seed}, {keyword}"
                        else:
                            # 随机生成：分类 + 随机3个关键词
                            num_keywords = min(3, len(keywords_list))
                            selected_keywords = random.sample(keywords_list, num_keywords)
                            selected_keywords.insert(0, tag_seed)
                            current_seed = ", ".join(selected_keywords)
                
                # 生成文章
                result = self.client.generate_article(current_seed, index, length)
                
                if isinstance(result, dict) and result.get('success'):
                    # 检查标题重复
                    if self.database.check_title_exists(result['title']):
                        # 标题重复：不入库，只记录错误
                        print(f"文章 {index} 标题重复，跳过入库: {result['title']}")
                        self.error_count += 1
                    else:
                        # 成功：保存到数据库
                        self.database.insert_article(
                            title=result['title'],
                            tags=result['tags'],
                            content=result['content'],
                            tag_seed=current_seed,
                            status='completed'
                        )
                        self.success_count += 1
                else:
                    # 失败：不入库，只记录错误
                    error_msg = result.get('error', '未知错误') if isinstance(result, dict) else str(result)
                    print(f"文章 {index} 生成失败，跳过入库: {error_msg}")
                    self.error_count += 1
                
                self.current_article += 1
                
                # 更新进度
                if progress_callback:
                    try:
                        progress_callback(
                            current=self.current_article,
                            total=count,
                            success=self.success_count,
                            errors=self.error_count,
                            rate_remaining=self.client.get_remaining_rate()
                        )
                    except Exception as e:
                        print(f"进度回调错误: {e}")

            except Exception as e:
                print(f"处理文章 {index} 时发生严重错误: {e}")
                self.error_count += 1
                self.current_article += 1

        def generate_worker():
            """生成工作线程"""
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self.executor = executor
                futures = []
                
                if infinite_mode:
                    # 无限生成模式：持续提交任务直到停止
                    index = 1
                    while self.is_running:
                        futures.append(executor.submit(process_single_article, index))
                        index += 1
                        time.sleep(0.1)
                        
                        # 清理已完成的 futures
                        futures = [f for f in futures if not f.done()]
                else:
                    # 固定数量模式 - 使用 self.total_articles 而不是 count
                    for i in range(self.total_articles):
                        if not self.is_running:
                            break
                        futures.append(executor.submit(process_single_article, i + 1))
                        time.sleep(0.1)
                
                # 等待所有任务完成
                for future in as_completed(futures):
                    if not self.is_running and not infinite_mode:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    try:
                        future.result()
                    except Exception as e:
                        print(f"工作线程异常: {e}")

            self.batch_end_time = time.time()
            self.is_running = False
            
            # 通知完成
            if completion_callback and not infinite_mode:
                try:
                    completion_callback(
                        total=count,
                        success=self.success_count,
                        errors=self.error_count
                    )
                except Exception as e:
                    print(f"完成回调错误: {e}")
        
        # 后台运行
        thread = threading.Thread(target=generate_worker, daemon=True)
        thread.start()
    
    def stop_generation(self):
        """停止生成"""
        self.is_running = False
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
    
    def get_status(self) -> dict:
        """获取当前状态"""
        current_time = time.time()
        
        if self.is_running:
            elapsed = current_time - self.batch_start_time
        elif self.batch_start_time > 0:
            end_time = self.batch_end_time if self.batch_end_time > 0 else current_time
            elapsed = end_time - self.batch_start_time
        else:
            elapsed = 0
        
        elapsed = max(0, elapsed)
        processed_count = self.success_count + self.error_count
        avg_time = elapsed / processed_count if processed_count > 0 else 0

        return {
            'is_running': self.is_running,
            'current': self.current_article,
            'total': self.total_articles,
            'success': self.success_count,
            'errors': self.error_count,
            'rate_remaining': self.client.get_remaining_rate(),
            'elapsed_time': elapsed,
            'avg_time': avg_time
        }
    
    def get_articles_paginated(self, page: int = 1, per_page: int = 10, filter_read: str = 'all',
                              search_title: str = '', search_tags: str = '', filter_status: str = 'all',
                              sort_field: str = 'created_at', sort_order: str = 'desc') -> dict:
        """获取分页文章列表"""
        return self.database.get_articles_paginated(page, per_page, filter_read, search_title, search_tags, filter_status, sort_field, sort_order)
    
    def toggle_read_status(self, article_id: int) -> bool:
        """切换文章已读状态"""
        return self.database.toggle_read_status(article_id)
    
    def get_article(self, article_id: int) -> Optional[dict]:
        """获取单篇文章"""
        return self.database.get_article_by_id(article_id)

    def delete_article(self, article_id: int):
        """删除文章"""
        self.database.delete_article(article_id)

    def clear_database(self):
        """清空数据库"""
        self.database.clear_all_articles()

    def perform_correction(self) -> dict:
        """执行数据修正"""
        return self.database.perform_correction()

    def reorder_ids(self) -> dict:
        """根据创建时间重新排序 ID"""
        return self.database.reorder_ids()
