"""
数据库模块 - SQLite 文章存储
"""
import sqlite3
import os
import ast
from datetime import datetime
from typing import List, Dict, Optional, Any


# 标准表结构定义（确保所有操作使用相同的结构）
# 注意：{if_not_exists} 会被替换为 "IF NOT EXISTS" 或空字符串
ARTICLES_TABLE_SCHEMA = '''
    CREATE TABLE {if_not_exists} articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        tags TEXT NOT NULL,
        content TEXT NOT NULL,
        tag_seed TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        error_message TEXT,
        is_read INTEGER DEFAULT 0
    )
'''

# 标准索引定义
ARTICLES_INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at DESC)',
    'CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title)',
    'CREATE INDEX IF NOT EXISTS idx_articles_tag_seed_created_at ON articles(tag_seed, created_at DESC)',
    'CREATE INDEX IF NOT EXISTS idx_articles_read_created ON articles(is_read, created_at DESC)'
]


class Database:
    """数据库操作类"""
    
    def __init__(self, db_path: str = "data/articles.db"):
        """初始化数据库连接并创建表"""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 使用标准表结构创建表
        cursor.execute(ARTICLES_TABLE_SCHEMA.format(if_not_exists='IF NOT EXISTS'))
        
        # 检查并添加 is_read 字段（兼容旧数据库）
        cursor.execute("PRAGMA table_info(articles)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'is_read' not in columns:
            cursor.execute('ALTER TABLE articles ADD COLUMN is_read INTEGER DEFAULT 0')
        
        # 创建所有标准索引
        for index_sql in ARTICLES_INDEXES:
            cursor.execute(index_sql)
        
        conn.commit()
        conn.close()
    
    def _normalize_title_and_tags(self, title: str, tags) -> (str, str):
        new_title = title.replace('`', '') if '`' in title else title
        tags_list = []
        if isinstance(tags, str):
            raw = tags.strip()
            if raw.startswith('[') and raw.endswith(']'):
                try:
                    tags_list = ast.literal_eval(raw)
                except Exception:
                    tags_list = raw.replace('[', '').replace(']', '').split(',')
            else:
                tags_list = raw.split(',')
        elif isinstance(tags, (list, tuple)):
            tags_list = list(tags)
        else:
            tags_list = [str(tags)]

        cleaned_items = []
        for item in tags_list:
            s = str(item)
            for char in ['[', ']', '{', '}']:
                s = s.replace(char, '')
            s = s.strip().replace("'", "").replace('"', "")
            if s:
                cleaned_items.append(s)

        tags_str = ','.join(cleaned_items)
        return new_title, tags_str

    def insert_article(self, title: str, tags: List[str], content: str, 
                       tag_seed: str, status: str = 'completed', 
                       error_message: Optional[str] = None, is_read: int = 0) -> int:
        """Insert a new article and return its ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        title, tags_str = self._normalize_title_and_tags(title, tags)
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO articles (title, tags, content, tag_seed, created_at, status, error_message, is_read)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, tags_str, content, tag_seed, created_at, status, error_message, is_read))
        
        article_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return article_id
    
    def get_all_articles(self) -> List[dict]:
        """Get all articles from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM articles ORDER BY created_at DESC')
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            article = dict(row)
            # Parse tags from string if needed
            if isinstance(article['tags'], str):
                try:
                    # Try to evaluate as list if it looks like one
                    if article['tags'].startswith('[') and article['tags'].endswith(']'):
                        import ast
                        article['tags'] = ast.literal_eval(article['tags'])
                except:
                    pass
            articles.append(article)
            
        conn.close()
        return articles

    def get_articles_paginated(self, page: int = 1, per_page: int = 10, filter_read: str = 'all', 
                              search_title: str = '', search_tags: str = '', filter_status: str = 'all',
                              sort_field: str = 'created_at', sort_order: str = 'desc') -> Dict[str, Any]:
        """获取分页文章列表（支持多条件筛选和排序）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        offset = (page - 1) * per_page
        
        # 构建筛选条件
        where_clauses = []
        params = []
        
        # 已读/未读筛选
        if filter_read == 'read':
            where_clauses.append('is_read = 1')
        elif filter_read == 'unread':
            where_clauses.append('is_read = 0')
        
        # 标题模糊搜索
        if search_title:
            where_clauses.append('title LIKE ?')
            params.append(f'%{search_title}%')
        
        # 标签模糊搜索
        if search_tags:
            where_clauses.append('tags LIKE ?')
            params.append(f'%{search_tags}%')
        
        # 状态筛选
        if filter_status == 'completed':
            where_clauses.append('status = "completed"')
        elif filter_status == 'failed':
            where_clauses.append('status = "failed"')
        
        where_clause = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''
        
        # 验证排序字段（防止 SQL 注入）
        allowed_sort_fields = {'id', 'title', 'created_at', 'status'}
        if sort_field not in allowed_sort_fields:
            sort_field = 'created_at'
        
        # 验证排序方向
        sort_order = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
        
        # 获取总数
        cursor.execute(f'SELECT COUNT(*) FROM articles {where_clause}', params)
        total_count = cursor.fetchone()[0]
        
        # 获取分页数据（不查询 content 字段，提升性能）
        cursor.execute(f'''
            SELECT id, title, tags, tag_seed, created_at, status, error_message, is_read 
            FROM articles {where_clause} 
            ORDER BY {sort_field} {sort_order}
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset])
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            article = dict(row)
            # 解析标签
            if isinstance(article['tags'], str):
                try:
                    if article['tags'].startswith('[') and article['tags'].endswith(']'):
                        import ast
                        article['tags'] = ast.literal_eval(article['tags'])
                except:
                    pass
            articles.append(article)
            
        conn.close()
        
        total_pages = (total_count + per_page - 1) // per_page
        
        return {
            'articles': articles,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        }
    
    def toggle_read_status(self, article_id: int) -> bool:
        """切换文章已读状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取当前状态
        cursor.execute('SELECT is_read FROM articles WHERE id = ?', (article_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False
        
        # 切换状态
        new_status = 0 if row[0] == 1 else 1
        cursor.execute('UPDATE articles SET is_read = ? WHERE id = ?', (new_status, article_id))
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_article_by_id(self, article_id: int) -> Optional[Dict]:
        """Get a single article by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        article = dict(row)
        if isinstance(article.get('tags'), str):
            try:
                if article['tags'].startswith('[') and article['tags'].endswith(']'):
                    import ast
                    article['tags'] = ast.literal_eval(article['tags'])
            except:
                pass
        
        conn.close()
        return article
    
    def check_title_exists(self, title: str) -> bool:
        """Check if an article with the same title already exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM articles WHERE title = ?', (title,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None
    
    def get_articles_by_seed(self, tag_seed: str) -> List[Dict]:
        """Retrieve articles by tag seed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM articles WHERE tag_seed = ? ORDER BY created_at DESC', (tag_seed,))
        rows = cursor.fetchall()
        
        conn.close()
        
        articles = []
        for row in rows:
            article = dict(row)
            if isinstance(article['tags'], str):
                 try:
                     if article['tags'].startswith('[') and article['tags'].endswith(']'):
                         import ast
                         article['tags'] = ast.literal_eval(article['tags'])
                 except:
                     pass
            articles.append(article)
        
        return articles
    
    def update_article_status(self, article_id: int, status: str, error_message: Optional[str] = None):
        """Update article status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE articles SET status = ?, error_message = ? WHERE id = ?
        ''', (status, error_message, article_id))
        
        conn.commit()
        conn.close()
    
    def get_article_count(self) -> int:
        """Get total article count."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM articles')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def delete_article(self, article_id: int):
        """Delete a specific article by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM articles WHERE id = ?', (article_id,))
        
        conn.commit()
        conn.close()

    def clear_all_articles(self):
        """Clear all articles from database and reset ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM articles')
        # Reset AUTOINCREMENT sequence
        cursor.execute('DELETE FROM sqlite_sequence WHERE name="articles"')
        
        conn.commit()
        conn.close()

    def perform_correction(self) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stats = {
            'deleted_count': 0,
            'duplicate_groups': 0,
            'tags_cleaned': 0,
            'titles_cleaned': 0,
            'failed_deleted': 0
        }
        
        cursor.execute('''
            SELECT title, COUNT(*) as count 
            FROM articles 
            GROUP BY title 
            HAVING count > 1
        ''')
        duplicates = cursor.fetchall()
        stats['duplicate_groups'] = len(duplicates)
        
        for dup in duplicates:
            title = dup['title']
            # Get all IDs for this title, ordered by created_at (earliest first)
            cursor.execute('SELECT id FROM articles WHERE title = ? ORDER BY created_at ASC, id ASC', (title,))
            ids = [row['id'] for row in cursor.fetchall()]
            
            if len(ids) > 1:
                # Keep the first one, delete the rest
                ids_to_delete = ids[1:]
                placeholders = ','.join('?' * len(ids_to_delete))
                cursor.execute(f'DELETE FROM articles WHERE id IN ({placeholders})', ids_to_delete)
                stats['deleted_count'] += len(ids_to_delete)

        cursor.execute('SELECT COUNT(*) FROM articles WHERE status = "failed"')
        failed_before = cursor.fetchone()[0]
        if failed_before > 0:
            cursor.execute('DELETE FROM articles WHERE status = "failed"')
            stats['failed_deleted'] = failed_before
        
        cursor.execute('SELECT id, title, tags FROM articles')
        rows = cursor.fetchall()
        
        for row in rows:
            article_id = row['id']
            title = row['title']
            tags_val = row['tags']
            
            new_title, new_tags = self._normalize_title_and_tags(title, tags_val)

            if new_title != title:
                stats['titles_cleaned'] += 1
            if new_tags != tags_val:
                stats['tags_cleaned'] += 1

            if new_title != title or new_tags != tags_val:
                cursor.execute('UPDATE articles SET title = ?, tags = ? WHERE id = ?', (new_title, new_tags, article_id))
        
        conn.commit()
        conn.close()
        return stats

    def reorder_ids(self) -> Dict[str, int]:
        """根据创建时间重新排序 ID（升序）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 获取所有文章，按创建时间升序排列
            cursor.execute('SELECT * FROM articles ORDER BY created_at ASC, id ASC')
            articles = cursor.fetchall()
            
            if not articles:
                conn.close()
                return {'reordered_count': 0}
            
            # 使用标准表结构创建新表（不使用 IF NOT EXISTS）
            cursor.execute(ARTICLES_TABLE_SCHEMA.format(if_not_exists='').replace('articles', 'articles_new'))
            
            # 按顺序插入到新表（包含所有字段）
            for article in articles:
                # 安全获取 is_read 字段（兼容旧数据库）
                try:
                    is_read = article['is_read'] if 'is_read' in article.keys() else 0
                except (KeyError, TypeError):
                    is_read = 0
                
                cursor.execute('''
                    INSERT INTO articles_new (title, tags, content, tag_seed, created_at, status, error_message, is_read)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (article['title'], article['tags'], article['content'], 
                      article['tag_seed'], article['created_at'], article['status'], 
                      article['error_message'], is_read))
            
            # 删除原表
            cursor.execute('DROP TABLE articles')
            
            # 重命名新表
            cursor.execute('ALTER TABLE articles_new RENAME TO articles')
            
            # 重建所有标准索引
            for index_sql in ARTICLES_INDEXES:
                cursor.execute(index_sql)
            
            # 重置自增序列
            cursor.execute('DELETE FROM sqlite_sequence WHERE name="articles_new"')
            cursor.execute('DELETE FROM sqlite_sequence WHERE name="articles"')
            cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES ("articles", ?)', (len(articles),))
            
            conn.commit()
            conn.close()
            
            return {'reordered_count': len(articles)}
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"ID 重排失败: {e}")
            raise
