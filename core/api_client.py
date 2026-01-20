"""
API 客户端 - MiMo API 调用和速率限制
"""
import os
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from openai import OpenAI


SYSTEM_MESSAGE = """
你现在是一个资深的文章编辑，请根据用户给出的内容标签和主题，创作一篇 Markdown 格式的中文博客文章。文章需要符合如下要求：
1. 标题：吸引力强，精准贴合主题
2. 内容结构：逻辑清晰、层次分明，包含不同核心章节（二级标题），内容需详实有干货，结合实用信息/案例/观点支撑，避免空洞表述
3. 语言风格：根据主题适配（如科技类专业严谨、生活类亲切自然），语句流畅，无晦涩表达，符合中文博客阅读习惯
4. 附加要求：结尾可增加总结性观点或互动引导（如提问、呼吁留言）

输出格式严格遵循以下规范：
# 文章标题

# Tags: {tags}

## 章节1：[章节标题1]
[章节1内容，需详实具体，可结合案例/数据/实用技巧等，段落清晰]

## 章节2：[章节标题2]
[章节2内容，逻辑承接上一章节，保持内容深度与实用性]

## 章节3：[章节标题3]
[章节3内容，可根据主题延伸补充，或展开对比分析/解决方案等]

（按需增减章节，核心章节不少于3个）
"""


class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, max_requests_per_minute: int = 100):
        """Initialize rate limiter."""
        self.max_requests = max_requests_per_minute
        self.requests = []
        self.lock = threading.Lock()
    
    def acquire(self):
        """Wait if necessary to stay within rate limit."""
        with self.lock:
            now = datetime.now()
            
            # Remove requests older than 1 minute
            minute_ago = now - timedelta(minutes=1)
            self.requests = [req_time for req_time in self.requests if req_time > minute_ago]
            
            # If we've reached the limit, wait
            if len(self.requests) >= self.max_requests:
                # Calculate wait time until oldest request expires
                oldest_request = min(self.requests)
                wait_time = (oldest_request - minute_ago).total_seconds() + 0.1
                if wait_time > 0:
                    time.sleep(wait_time)
                    # Clean up old requests after waiting
                    now = datetime.now()
                    minute_ago = now - timedelta(minutes=1)
                    self.requests = [req_time for req_time in self.requests if req_time > minute_ago]
            
            # Add current request (count it immediately before API call)
            self.requests.append(datetime.now())
    
    def get_remaining_requests(self) -> int:
        """Get remaining requests in current window."""
        with self.lock:
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            # 清理过期请求（确保显示准确）
            self.requests = [req_time for req_time in self.requests if req_time > minute_ago]
            return max(0, self.max_requests - len(self.requests))


class APIClient:
    """MiMo API 客户端"""
    
    def __init__(self, api_key: Optional[str] = None, 
                 base_url: str = "https://api.xiaomimimo.com/v1",
                 rate_limit: int = 100):
        """Initialize MiMo client."""
        self.api_key = api_key
        self.base_url = base_url.strip('`').strip()
        
        if not self.api_key:
            raise ValueError("API key not provided. Please set API key in settings.")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        self.rate_limiter = RateLimiter(rate_limit)
        self.model = "mimo-v2-flash"
    
    def generate_article(self, tag_seed: str, article_index: int = 1, length: str = "6000") -> Dict[str, Any]:
        """Generate a single article based on tag seed."""
        # Apply rate limiting
        self.rate_limiter.acquire()
        
        # Create system message
        
        system_message = SYSTEM_MESSAGE
        
        length_instruction = "约 6000 字以内" if length == "Max" else f"约 {length} 字以内"

        # Create user message with tag seed
        user_message = f"""
可选主题：{tag_seed}
文章长度：{length_instruction}
请根据内容主题选取几个或一个作为文章内容展开编写文章，文章长度控制在要求范围内。
"""
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                max_completion_tokens=8192,
                temperature=0.7,
                top_p=0.95,
                stream=False,
                stop=None,
                frequency_penalty=0,
                presence_penalty=0,
                extra_body={
                    "thinking": {"type": "disabled"}
                }
            )
            
            response_content = completion.choices[0].message.content
            
            # Parse the response to extract title, tags, and content
            parsed = self._parse_article(response_content)
            
            return {
                'success': True,
                'title': parsed['title'],
                'tags': parsed['tags'],
                'content': parsed['content'],
                'raw_response': response_content,
                'error': None
            }

        except Exception as e:
            return {
                'success': False,
                'title': '',
                'tags': [],
                'content': '',
                'raw_response': '',
                'error': str(e)
            }
    
    def _parse_article(self, content: str) -> Dict[str, Any]:
        """Parse article content to extract title and tags."""
        lines = content.strip().split('\n')
        
        title = ""
        tags = []
        article_content = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # 1. Extract Title
            if line_stripped.startswith('# ') and not title:
                title = line_stripped[2:].strip()
                # Don't add title line to content yet, we'll reconstruct it later
                continue

            # 2. Extract Tags (and skip this line in content)
            # Check for various tag prefixes
            is_tag_line = False
            tag_prefixes = ['**Tags:**', '**标签：**', 'Tags:', '标签：', '# Tags:', '# 标签：']
            
            for prefix in tag_prefixes:
                if line_stripped.startswith(prefix):
                    is_tag_line = True
                    tags_part = line_stripped[len(prefix):].strip()
                    if tags_part:
                        # Split by comma (both English and Chinese)
                        tags_part = tags_part.replace('，', ',')
                        current_tags = [tag.strip() for tag in tags_part.split(',') if tag.strip()]
                        tags.extend(current_tags)
                    break
            
            if is_tag_line:
                continue

            # 3. Add other lines to content
            article_content.append(line)
        
        # If no tags found, try to extract from content
        if not tags and '##' in content:
            # Generate some generic tags based on title
            words = title.split()
            if len(words) >= 2:
                tags = words[:2] + ['博客', '文章']
            else:
                tags = [title, '博客', '文章']
        
        # Reconstruct content
        # Remove empty lines at the beginning
        while article_content and not article_content[0].strip():
            article_content.pop(0)
            
        final_content = '\n'.join(article_content)
        
        # Add title back to the top
        if title:
             final_content = f"# {title}\n\n{final_content}"
        
        return {
            'title': title or 'Untitled Article',
            'tags': tags or ['博客', '文章'],
            'content': final_content
        }
    
    def get_remaining_rate(self) -> int:
        """Get remaining API requests."""
        return self.rate_limiter.get_remaining_requests()
