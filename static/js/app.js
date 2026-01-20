// Alpine.js Data Component
function appData() {
    return {
        // Markdown renderer
        md: null,
        
        // Toast notifications
        toasts: [],
        toastId: 0,
        
        // Confirm dialog
        confirmDialog: {
            show: false,
            title: '',
            message: '',
            onConfirm: null,
            confirmText: '确定',
            cancelText: '取消',
            type: 'warning'
        },
        
        // State
        tags: [],
        tagSeed: '',
        customTag: false,
        articleCount: 100,
        infiniteMode: false,
        length: 'Max',
        sequential: false,
        
        articles: [],
        currentPage: 1,
        totalPages: 1,
        totalCount: 0,
        perPage: 10,
        filterRead: 'all',
        searchTitle: '',
        searchTags: '',
        filterStatus: 'all',
        sortField: 'created_at',
        sortOrder: 'desc',
        
        status: {
            is_running: false,
            current: 0,
            total: 0,
            success: 0,
            errors: 0,
            rate_remaining: 100,
            elapsed_time: 0,
            avg_time: 0
        },
        
        isGenerating: false,
        pollInterval: null,
        rateTimer: 60,
        
        currentArticle: {
            title: '',
            content: ''
        },
        currentArticleRaw: '',
        
        settings: {
            api_key: '',
            max_workers: 3
        },
        showKey: false,
        
        showArticle: false,
        showSettings: false,
        showSummary: false,
        
        summary: {
            total: 0,
            success: 0,
            errors: 0,
            elapsed_time: 0,
            avg_time: 0
        },
        
        // Toast notification methods
        showToast(message, type = 'info', duration = 3000) {
            const id = ++this.toastId;
            const toast = { id, message, type, show: true };
            this.toasts.push(toast);
            
            // Auto remove after duration
            setTimeout(() => {
                this.removeToast(id);
            }, duration);
        },
        
        removeToast(id) {
            const index = this.toasts.findIndex(t => t.id === id);
            if (index !== -1) {
                this.toasts[index].show = false;
                // Remove from array after animation
                setTimeout(() => {
                    this.toasts = this.toasts.filter(t => t.id !== id);
                }, 300);
            }
        },
        
        // Confirm dialog methods
        showConfirm(message, title = '确认操作', type = 'warning') {
            return new Promise((resolve) => {
                this.confirmDialog = {
                    show: true,
                    title,
                    message,
                    type,
                    confirmText: '确定',
                    cancelText: '取消',
                    onConfirm: () => {
                        this.confirmDialog.show = false;
                        resolve(true);
                    },
                    onCancel: () => {
                        this.confirmDialog.show = false;
                        resolve(false);
                    }
                };
            });
        },
        
        // Initialize
        async init() {
            // Initialize markdown-it
            if (window.markdownit) {
                this.md = window.markdownit({
                    html: true,
                    linkify: true,
                    typographer: true
                });
            } else {
                console.error('markdown-it not loaded');
            }
            
            // 从 localStorage 恢复排序设置
            const savedSortField = localStorage.getItem('sortField');
            const savedSortOrder = localStorage.getItem('sortOrder');
            if (savedSortField) this.sortField = savedSortField;
            if (savedSortOrder) this.sortOrder = savedSortOrder;
            
            await this.loadArticles(1);
            await this.loadTags();
            await this.loadSettings();
            this.checkStatus();
            
            // Start rate timer
            setInterval(() => {
                const now = new Date();
                this.rateTimer = 60 - now.getSeconds();
            }, 1000);
        },
        
        // Load Tags
        async loadTags() {
            try {
                const response = await fetch('/api/tags');
                this.tags = await response.json();
            } catch (error) {
                console.error('Failed to load tags:', error);
            }
        },
        
        // Select Tag
        selectTag(tag) {
            if (tag === '自定义') {
                this.tagSeed = '';
                this.customTag = true;
            } else {
                this.tagSeed = tag;
                this.customTag = false;
            }
        },
        
        // Load Articles
        async loadArticles(page = 1) {
            try {
                const params = new URLSearchParams({
                    page: page,
                    per_page: this.perPage,
                    filter: this.filterRead,
                    search_title: this.searchTitle,
                    search_tags: this.searchTags,
                    filter_status: this.filterStatus,
                    sort_field: this.sortField,
                    sort_order: this.sortOrder
                });
                
                const response = await fetch(`/api/articles?${params}`);
                const data = await response.json();
                
                this.articles = data.articles || [];
                this.currentPage = data.page || 1;
                this.totalPages = data.total_pages || 1;
                this.totalCount = data.total_count || 0;
            } catch (error) {
                console.error('Failed to load articles:', error);
            }
        },
        
        // Toggle Sort
        toggleSort(field) {
            if (this.sortField === field) {
                // 同一字段，切换排序方向
                this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                // 不同字段，设置新字段并默认降序
                this.sortField = field;
                this.sortOrder = 'desc';
            }
            // 保存到 localStorage
            localStorage.setItem('sortField', this.sortField);
            localStorage.setItem('sortOrder', this.sortOrder);
            this.loadArticles(1);
        },
        
        // Clear Filters
        clearFilters() {
            this.searchTitle = '';
            this.searchTags = '';
            this.filterRead = 'all';
            this.filterStatus = 'all';
            this.sortField = 'created_at';
            this.sortOrder = 'desc';
            this.loadArticles(1);
        },
        
        // Toggle Read Status
        async toggleRead(articleId) {
            try {
                const response = await fetch(`/api/article/${articleId}/toggle-read`, { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    // 更新本地状态
                    const article = this.articles.find(a => a.id === articleId);
                    if (article) {
                        article.is_read = article.is_read ? 0 : 1;
                    }
                }
            } catch (error) {
                console.error('Failed to toggle read status:', error);
            }
        },
        
        // Pagination
        get visiblePages() {
            const pages = [];
            const total = this.totalPages;
            const current = this.currentPage;
            
            // 如果总页数少于等于7，显示所有页码
            if (total <= 7) {
                for (let i = 1; i <= total; i++) {
                    pages.push(i);
                }
                return pages;
            }
            
            // 总页数大于7的情况
            // 总是显示第一页
            pages.push(1);
            
            // 计算要显示的中间页码范围
            let rangeStart, rangeEnd;
            
            if (current <= 3) {
                // 当前页在前面，显示 1 2 3 4 5 ... last
                rangeStart = 2;
                rangeEnd = 5;
            } else if (current >= total - 2) {
                // 当前页在后面，显示 1 ... (total-4) (total-3) (total-2) (total-1) total
                rangeStart = total - 4;
                rangeEnd = total - 1;
            } else {
                // 当前页在中间，显示 1 ... (current-1) current (current+1) ... total
                rangeStart = current - 1;
                rangeEnd = current + 1;
            }
            
            // 添加左侧省略号
            if (rangeStart > 2) {
                pages.push('left-ellipsis');
            }
            
            // 添加中间的页码
            for (let i = rangeStart; i <= rangeEnd; i++) {
                pages.push(i);
            }
            
            // 添加右侧省略号
            if (rangeEnd < total - 1) {
                pages.push('right-ellipsis');
            }
            
            // 总是显示最后一页
            pages.push(total);
            
            return pages;
        },
        
        // Format helpers
        formatTags(tags) {
            if (Array.isArray(tags)) {
                return tags.join('、');
            } else if (typeof tags === 'string') {
                return tags.replace(/,/g, '、');
            }
            return '';
        },
        
        formatTime(time) {
            if (!time) return '';
            let formatted = time.replace('T', ' ');
            if (formatted.length > 19) {
                formatted = formatted.substring(0, 19);
            }
            return formatted;
        },
        
        // Start Generation
        async startGeneration() {
            if (!this.tagSeed.trim()) {
                this.showToast('请输入或选择种子/主题', 'warning');
                return;
            }
            
            if (this.status.is_running) {
                this.showToast('生成已在进行中', 'warning');
                return;
            }
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tag_seed: this.tagSeed,
                        count: this.infiniteMode ? -1 : this.articleCount,
                        length: this.length,
                        sequential: this.sequential
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    this.showToast(data.error, 'error');
                } else {
                    this.isGenerating = true;
                    this.pollInterval = setInterval(() => this.checkStatus(), 1000);
                }
            } catch (error) {
                this.showToast('请求失败: ' + error, 'error');
            }
        },
        
        // Stop Generation
        async stopGeneration() {
            try {
                await fetch('/api/stop', { method: 'POST' });
            } catch (error) {
                console.error('Failed to stop generation:', error);
            }
        },
        
        // Check Status
        async checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.is_running) {
                    this.isGenerating = true;
                    this.status = data;
                    
                    if (!this.pollInterval) {
                        this.pollInterval = setInterval(() => this.checkStatus(), 1000);
                    }
                } else {
                    if (this.isGenerating) {
                        // Generation just finished
                        this.isGenerating = false;
                        this.status = data;
                        await this.loadArticles(1);
                        
                        // 只有非无限模式才显示摘要
                        if (data.total !== -1) {
                            this.displaySummary(data);
                        }
                    }
                    
                    if (this.pollInterval) {
                        clearInterval(this.pollInterval);
                        this.pollInterval = null;
                    }
                }
            } catch (error) {
                console.error('Failed to check status:', error);
            }
        },
        
        // Display Summary
        displaySummary(status) {
            this.summary = {
                total: status.total || 0,
                success: status.success || 0,
                errors: status.errors || 0,
                elapsed_time: status.elapsed_time || 0,
                avg_time: status.avg_time || 0
            };
            this.showSummary = true;
        },
        
        // Format duration helper (for elapsed time)
        formatDuration(seconds) {
            if (typeof seconds !== 'number' || isNaN(seconds)) {
                return '0s';
            }
            
            if (seconds < 60) {
                return `${seconds.toFixed(1)}s`;
            }
            const mins = Math.floor(seconds / 60);
            const secs = (seconds % 60).toFixed(1);
            return `${mins}m ${secs}s`;
        },
        
        // View Article
        async viewArticle(id) {
            try {
                const response = await fetch(`/api/article/${id}`);
                const article = await response.json();
                
                if (article.error) {
                    console.error('Article error:', article.error);
                    return;
                }
                
                this.currentArticle.title = article.title;
                this.currentArticleRaw = article.content || '';
                
                // Render markdown
                if (this.md) {
                    this.currentArticle.content = this.md.render(article.content || '');
                } else {
                    // Fallback to plain text
                    this.currentArticle.content = '<pre>' + (article.content || '') + '</pre>';
                }
                
                this.showArticle = true;
            } catch (error) {
                console.error('Failed to load article:', error);
                this.showToast('加载文章失败: ' + error.message, 'error');
            }
        },
        
        // Copy Content
        async copyContent() {
            try {
                await navigator.clipboard.writeText(this.currentArticleRaw);
                this.showToast('内容已复制到剪贴板', 'success');
            } catch (error) {
                console.error('Failed to copy:', error);
            }
        },
        
        // Export Markdown
        exportMarkdown() {
            try {
                // 创建 Blob 对象
                const blob = new Blob([this.currentArticleRaw], { type: 'text/markdown;charset=utf-8' });
                
                // 创建下载链接
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                
                // 使用文章标题作为文件名，移除特殊字符
                const safeTitle = this.currentArticle.title
                    .replace(/[<>:"/\\|?*]/g, '') // 移除 Windows 不允许的文件名字符
                    .replace(/\s+/g, '_')          // 空格替换为下划线
                    .substring(0, 100);            // 限制长度
                
                link.download = `${safeTitle}.md`;
                
                // 触发下载
                document.body.appendChild(link);
                link.click();
                
                // 清理
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
                
                this.showToast('Markdown 文件已导出', 'success');
            } catch (error) {
                console.error('Failed to export markdown:', error);
                this.showToast('导出失败: ' + error.message, 'error');
            }
        },
        
        // Delete Article
        async deleteArticle(id) {
            if (!await this.showConfirm('确定要删除这篇文章吗？', '删除文章', 'warning')) return;
            
            try {
                await fetch(`/api/article/${id}`, { method: 'DELETE' });
                await this.loadArticles(this.currentPage);
                this.showToast('文章已删除', 'success');
            } catch (error) {
                console.error('Failed to delete article:', error);
                this.showToast('删除失败', 'error');
            }
        },
        
        // Clear Database
        async clearDatabase() {
            if (!await this.showConfirm('确定要清空所有文章吗？此操作不可恢复！', '清空数据库', 'warning')) return;
            
            try {
                await fetch('/api/articles/clear', { method: 'POST' });
                await this.loadArticles(1);
                this.status = {
                    is_running: false,
                    current: 0,
                    total: 0,
                    success: 0,
                    errors: 0,
                    rate_remaining: 100,
                    elapsed_time: 0,
                    avg_time: 0
                };
                this.showToast('数据库已清空', 'success');
            } catch (error) {
                console.error('Failed to clear database:', error);
                this.showToast('清空失败', 'error');
            }
        },
        
        // Perform Correction
        async performCorrection() {
            if (!await this.showConfirm('确定要执行一键修正吗？这将删除重复文章、失败文章并清理格式。', '数据修正', 'info')) return;
            
            try {
                const response = await fetch('/api/articles/correction', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    const stats = data.stats;
                    this.showToast(
                        `修正完成！删除重复 ${stats.deleted_count || 0} 篇，删除失败 ${stats.failed_deleted || 0} 篇，清理标签 ${stats.tags_cleaned || 0} 个`,
                        'success',
                        5000
                    );
                    await this.loadArticles(1);
                } else {
                    this.showToast('修正失败', 'error');
                }
            } catch (error) {
                console.error('Failed to perform correction:', error);
            }
        },
        
        // Reorder IDs
        async reorderIds() {
            if (!await this.showConfirm('确定要重新排序 ID 吗？将根据创建时间重新分配 ID（时间早的 ID 小）。', 'ID 重排', 'info')) return;
            
            try {
                const response = await fetch('/api/articles/reorder', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    const stats = data.stats;
                    this.showToast(`ID 重排完成！已重新排序 ${stats.reordered_count || 0} 篇文章`, 'success', 4000);
                    await this.loadArticles(1);
                } else {
                    this.showToast('ID 重排失败', 'error');
                }
            } catch (error) {
                console.error('Failed to reorder IDs:', error);
            }
        },
        
        // Load Settings
        async loadSettings() {
            try {
                const response = await fetch('/api/settings');
                this.settings = await response.json();
                
                // 如果没有 API Key，自动打开设置并提示
                if (!this.settings.api_key) {
                    this.showSettings = true;
                    setTimeout(() => {
                        this.showToast('欢迎使用！请先配置 API Key 以开始生成文章', 'info', 6000);
                    }, 300);
                }
            } catch (error) {
                console.error('Failed to load settings:', error);
            }
        },
        
        // Save Settings
        async saveSettings() {
            if (!this.settings.api_key.trim()) {
                this.showToast('API Key 不能为空', 'warning');
                return;
            }
            
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    this.showToast('设置已保存', 'success');
                    this.showSettings = false;
                } else {
                    this.showToast('保存失败', 'error');
                }
            } catch (error) {
                this.showToast('保存失败: ' + error, 'error');
            }
        }
    };
}
