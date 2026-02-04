// ========================================
// Lifeline - Main Application JS
// ========================================

const API_BASE = '/api';

// Auth helpers
const auth = {
    getToken() {
        return localStorage.getItem('token');
    },
    
    setToken(token) {
        localStorage.setItem('token', token);
    },
    
    removeToken() {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    },
    
    getUser() {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    },
    
    setUser(user) {
        localStorage.setItem('user', JSON.stringify(user));
        // Apply theme when user is set
        if (user && user.theme) {
            themeManager.apply(user.theme);
        }
    },
    
    isLoggedIn() {
        return !!this.getToken();
    },
    
    logout() {
        this.removeToken();
        window.location.href = '/login';
    }
};

// Theme Manager
const themeManager = {
    apply(theme) {
        document.body.classList.remove('theme-light', 'theme-dark');
        if (theme === 'light') {
            document.body.classList.add('theme-light');
        }
        localStorage.setItem('theme', theme);
    },
    
    get() {
        return localStorage.getItem('theme') || 'dark';
    },
    
    toggle() {
        const current = this.get();
        const newTheme = current === 'dark' ? 'light' : 'dark';
        this.apply(newTheme);
        return newTheme;
    },
    
    init() {
        // Apply saved theme immediately on page load
        const savedTheme = this.get();
        this.apply(savedTheme);
    }
};

// Apply theme immediately (before DOMContentLoaded)
themeManager.init();

// API helpers
async function apiRequest(endpoint, options = {}) {
    const token = auth.getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });
    
    if (response.status === 401) {
        auth.logout();
        throw new Error('Unauthorized');
    }
    
    if (!response.ok) {
        let message = 'Request failed';
        const contentType = response.headers.get('content-type');
        
        try {
            if (contentType && contentType.includes('application/json')) {
                const error = await response.json();
                if (error.detail) {
                    if (typeof error.detail === 'string') {
                        message = error.detail;
                    } else if (Array.isArray(error.detail)) {
                        // FastAPI validation errors
                        message = error.detail.map(e => e.msg || JSON.stringify(e)).join(', ');
                    } else {
                        message = JSON.stringify(error.detail);
                    }
                } else if (error.message) {
                    message = error.message;
                }
            } else {
                // Server returned HTML or other non-JSON response
                const text = await response.text();
                if (text.includes('Internal Server Error')) {
                    message = 'Internal Server Error. Please check server logs.';
                } else {
                    message = `Server error: ${response.status} ${response.statusText}`;
                }
            }
        } catch (parseError) {
            message = `Server error: ${response.status} ${response.statusText}`;
        }
        
        throw new Error(message);
    }
    
    return response.json();
}

const api = {
    // Auth
    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        return response.json();
    },
    
    async register(userData) {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }
        
        return response.json();
    },
    
    async getMe() {
        return apiRequest('/auth/me');
    },
    
    getCurrentUser() {
        return this.getMe();
    },
    
    // Users (admin only)
    async getUsers() {
        return apiRequest('/users/');
    },
    
    async getUser(userId) {
        return apiRequest(`/users/${userId}`);
    },
    
    async createUser(userData) {
        return apiRequest('/users/', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    },
    
    async updateUser(userId, userData) {
        return apiRequest(`/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(userData)
        });
    },
    
    async deleteUser(userId) {
        return apiRequest(`/users/${userId}`, { method: 'DELETE' });
    },
    
    async blockUser(userId) {
        return apiRequest(`/users/${userId}/block`, { method: 'POST' });
    },
    
    async unblockUser(userId) {
        return apiRequest(`/users/${userId}/unblock`, { method: 'POST' });
    },
    
    async getUserProjects(userId) {
        return apiRequest(`/users/${userId}/projects`);
    },
    
    async updateUserProjects(userId, projectsData) {
        return apiRequest(`/users/${userId}/projects`, {
            method: 'PUT',
            body: JSON.stringify(projectsData)
        });
    },
    
    // Organizations
    async getOrganizations() {
        return apiRequest('/organizations/');
    },
    
    async getOrganization(id) {
        return apiRequest(`/organizations/${id}`);
    },
    
    async createOrganization(data) {
        return apiRequest('/organizations/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateOrganization(id, data) {
        return apiRequest(`/organizations/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteOrganization(id) {
        return apiRequest(`/organizations/${id}`, { method: 'DELETE' });
    },
    
    async getOrganizationDepartments(organizationId) {
        return apiRequest(`/organizations/${organizationId}/departments`);
    },
    
    // Departments
    async getDepartments(organizationId = null) {
        const url = organizationId 
            ? `/departments/?organization_id=${organizationId}`
            : '/departments/';
        return apiRequest(url);
    },
    
    async getDepartment(id) {
        return apiRequest(`/departments/${id}`);
    },
    
    async createDepartment(data) {
        return apiRequest('/departments/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateDepartment(id, data) {
        return apiRequest(`/departments/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteDepartment(id) {
        return apiRequest(`/departments/${id}`, { method: 'DELETE' });
    },
    
    // Roles
    async getRoles() {
        return apiRequest('/roles/');
    },
    
    async getRole(id) {
        return apiRequest(`/roles/${id}`);
    },
    
    async createRole(data) {
        return apiRequest('/roles/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateRole(id, data) {
        return apiRequest(`/roles/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteRole(id) {
        return apiRequest(`/roles/${id}`, { method: 'DELETE' });
    },
    
    // Field Permissions
    async getFieldPermissions(projectId, fieldDefinitionId = null, stageId = null, roleId = null) {
        let url = `/field-permissions/project/${projectId}`;
        const params = [];
        if (fieldDefinitionId) params.push(`field_definition_id=${fieldDefinitionId}`);
        if (stageId) params.push(`stage_id=${stageId}`);
        if (roleId) params.push(`role_id=${roleId}`);
        if (params.length > 0) url += '?' + params.join('&');
        return apiRequest(url);
    },
    
    async checkFieldPermissions(taskId) {
        return apiRequest(`/field-permissions/task/${taskId}/check`);
    },
    
    async createFieldPermission(data) {
        return apiRequest('/field-permissions/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateFieldPermission(id, data) {
        return apiRequest(`/field-permissions/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteFieldPermission(id) {
        return apiRequest(`/field-permissions/${id}`, { method: 'DELETE' });
    },
    
    async createBulkFieldPermissions(permissions) {
        return apiRequest('/field-permissions/bulk', {
            method: 'POST',
            body: JSON.stringify(permissions)
        });
    },
    
    // Notifications
    async getNotifications(unreadOnly = false, limit = 50) {
        return apiRequest(`/notifications/?unread_only=${unreadOnly}&limit=${limit}`);
    },
    
    async getUnreadNotificationsCount() {
        return apiRequest('/notifications/unread-count');
    },
    
    async markNotificationAsRead(id) {
        return apiRequest(`/notifications/${id}/read`, { method: 'POST' });
    },
    
    async markAllNotificationsAsRead() {
        return apiRequest('/notifications/read-all', { method: 'POST' });
    },
    
    async deleteNotification(id) {
        return apiRequest(`/notifications/${id}`, { method: 'DELETE' });
    },
    
    async deleteAllNotifications() {
        return apiRequest('/notifications/delete-all', { method: 'DELETE' });
    },
    
    // My profile
    async updateMyProfile(userData) {
        return apiRequest('/auth/me', {
            method: 'PUT',
            body: JSON.stringify(userData)
        });
    },
    
    // Settings
    async getTelegramBotSettings() {
        return apiRequest('/settings/telegram-bot');
    },
    
    async updateTelegramBotSettings(data) {
        return apiRequest('/settings/telegram-bot', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async testTelegramBot() {
        return apiRequest('/settings/telegram-bot/test', {
            method: 'POST'
        });
    },
    
    // Projects
    async getProjects() {
        return apiRequest('/projects/');
    },
    
    async getProject(id) {
        return apiRequest(`/projects/${id}`);
    },
    
    async createProject(data) {
        return apiRequest('/projects/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateProject(id, data) {
        return apiRequest(`/projects/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteProject(id) {
        return apiRequest(`/projects/${id}`, { method: 'DELETE' });
    },
    
    // Stages
    async createStage(projectId, data) {
        return apiRequest(`/projects/${projectId}/stages`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateStage(projectId, stageId, data) {
        return apiRequest(`/projects/${projectId}/stages/${stageId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteStage(projectId, stageId) {
        return apiRequest(`/projects/${projectId}/stages/${stageId}`, {
            method: 'DELETE'
        });
    },
    
    async reorderStages(projectId, stageOrders) {
        return apiRequest(`/projects/${projectId}/stages/reorder`, {
            method: 'PUT',
            body: JSON.stringify(stageOrders)
        });
    },
    
    // Stage Transitions
    async getTransitions(projectId) {
        return apiRequest(`/projects/${projectId}/transitions`);
    },
    
    async createTransition(projectId, data) {
        return apiRequest(`/projects/${projectId}/transitions`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async deleteTransition(projectId, transitionId) {
        return apiRequest(`/projects/${projectId}/transitions/${transitionId}`, {
            method: 'DELETE'
        });
    },
    
    async getAllowedTransitions(projectId, stageId) {
        return apiRequest(`/projects/${projectId}/stages/${stageId}/allowed-transitions`);
    },
    
    // Field Groups
    async getFieldGroups(projectId) {
        return apiRequest(`/projects/${projectId}/field-groups`);
    },
    
    async createFieldGroup(projectId, data) {
        return apiRequest(`/projects/${projectId}/field-groups`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateFieldGroup(projectId, groupId, data) {
        return apiRequest(`/projects/${projectId}/field-groups/${groupId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteFieldGroup(projectId, groupId) {
        return apiRequest(`/projects/${projectId}/field-groups/${groupId}`, {
            method: 'DELETE'
        });
    },
    
    // Fields
    async createField(projectId, data) {
        return apiRequest(`/projects/${projectId}/fields`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async updateField(projectId, fieldId, data) {
        return apiRequest(`/projects/${projectId}/fields/${fieldId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async deleteField(projectId, fieldId) {
        return apiRequest(`/projects/${projectId}/fields/${fieldId}`, {
            method: 'DELETE'
        });
    },
    
    // Permissions
    async getProjectPermissions(projectId) {
        return apiRequest(`/projects/${projectId}/permissions`);
    },
    
    async addProjectPermission(projectId, data) {
        return apiRequest(`/projects/${projectId}/permissions`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async deleteProjectPermission(projectId, permissionId) {
        return apiRequest(`/projects/${projectId}/permissions/${permissionId}`, {
            method: 'DELETE'
        });
    },
    
    // Tasks
    async getTasks(projectId, filters = {}) {
        const params = new URLSearchParams({ project_id: projectId });
        Object.entries(filters).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== '') {
                params.append(key, value);
            }
        });
        return apiRequest(`/tasks/?${params}`);
    },
    
    async getKanbanData(projectId) {
        return apiRequest(`/tasks/kanban/${projectId}`);
    },
    
    async createTask(data) {
        return apiRequest('/tasks/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async getTask(id) {
        return apiRequest(`/tasks/${id}`);
    },
    
    async updateTask(id, data) {
        return apiRequest(`/tasks/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    async moveTask(taskId, stageId) {
        return apiRequest(`/tasks/${taskId}/stage/${stageId}`, {
            method: 'PATCH'
        });
    },
    
    async deleteTask(id) {
        return apiRequest(`/tasks/${id}`, { method: 'DELETE' });
    },
    
    // Attachments
    async getTaskAttachments(taskId) {
        return apiRequest(`/attachments/task/${taskId}`);
    },
    
    async getTaskHistory(taskId) {
        return apiRequest(`/tasks/${taskId}/history`);
    },
    
    async getProjectHistory(projectId, filters = {}) {
        const params = new URLSearchParams();
        if (filters.task_id) params.append('task_id', filters.task_id);
        if (filters.user_id) params.append('user_id', filters.user_id);
        if (filters.action) params.append('action', filters.action);
        if (filters.limit) params.append('limit', filters.limit);
        return apiRequest(`/tasks/project/${projectId}/history?${params}`);
    },
    
    // Task Comments
    async getTaskComments(taskId) {
        return apiRequest(`/tasks/${taskId}/comments`);
    },
    
    async createComment(taskId, message, replyToId = null) {
        const body = { message };
        if (replyToId) body.reply_to_id = replyToId;
        return apiRequest(`/tasks/${taskId}/comments`, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    },
    
    async updateComment(taskId, commentId, message) {
        return apiRequest(`/tasks/${taskId}/comments/${commentId}`, {
            method: 'PUT',
            body: JSON.stringify({ message })
        });
    },
    
    async deleteComment(taskId, commentId) {
        return apiRequest(`/tasks/${taskId}/comments/${commentId}`, {
            method: 'DELETE'
        });
    },
    
    async uploadAttachment(taskId, file) {
        const token = auth.getToken();
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE}/attachments/task/${taskId}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
        
        return response.json();
    },
    
    async deleteAttachment(attachmentId) {
        return apiRequest(`/attachments/${attachmentId}`, { method: 'DELETE' });
    },
    
    getAttachmentViewUrl(attachmentId) {
        const token = auth.getToken();
        return `${API_BASE}/attachments/${attachmentId}/view?token=${encodeURIComponent(token)}`;
    },
    
    getAttachmentDownloadUrl(attachmentId) {
        const token = auth.getToken();
        return `${API_BASE}/attachments/${attachmentId}/download?token=${encodeURIComponent(token)}`;
    },
    
    // Task Links
    async getTaskLinks(taskId) {
        return apiRequest(`/task-links/${taskId}`);
    },
    
    async createTaskLink(data) {
        return apiRequest('/task-links/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    async deleteTaskLink(linkId) {
        return apiRequest(`/task-links/${linkId}`, { method: 'DELETE' });
    },
    
    async getLinkTypes() {
        return apiRequest('/task-links/types');
    },
    
    async getTaskLinksChain(taskId, includeArchived = false) {
        return apiRequest(`/task-links/task/${taskId}/chain?include_archived=${includeArchived}`);
    }
};

// UI helpers
function showAlert(message, type = 'error') {
    // Создаем контейнер для уведомлений, если его еще нет
    let alertContainer = document.getElementById('alert-container');
    if (!alertContainer) {
        alertContainer = document.createElement('div');
        alertContainer.id = 'alert-container';
        document.body.appendChild(alertContainer);
    }
    
    // Удаляем существующее уведомление того же типа (опционально)
    const existing = alertContainer.querySelector(`.alert-${type}`);
    if (existing) existing.remove();
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    
    alertContainer.appendChild(alert);
    
    // Анимация появления
    setTimeout(() => {
        alert.classList.add('show');
    }, 10);
    
    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 300);
    }, 5000);
}

function showLoading(container) {
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

function formatDateTime(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getPriorityLabel(priority) {
    const labels = ['Низкий', 'Обычный', 'Высокий', 'Критичный'];
    return labels[priority] || 'Обычный';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getInitials(name) {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
}

// Modal management
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.querySelector('.modal-overlay.active');
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
});

// Update navbar user info
function updateNavbar() {
    const user = auth.getUser();
    const userMenu = document.querySelector('.user-menu');
    
    if (userMenu && user) {
        userMenu.innerHTML = `
            <a href="/profile" class="user-name-link" style="cursor: pointer; text-decoration: none; color: var(--text-secondary); transition: color 0.2s;">
                <span class="text-secondary">${user.full_name || user.username}</span>
            </a>
            <div class="notification-icon-wrapper" style="position: relative;">
                <button class="btn btn-ghost btn-sm notification-btn" onclick="openNotificationsModal()" title="Уведомления">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                    </svg>
                    <span class="notification-badge" style="display: none;">0</span>
                </button>
            </div>
            <a href="/profile" class="user-avatar-link" style="cursor: pointer; text-decoration: none;">
                <div class="user-avatar">${getInitials(user.full_name || user.username)}</div>
            </a>
            <button class="btn btn-ghost btn-sm" onclick="auth.logout()">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
                </svg>
            </button>
        `;
        
        // Create notifications modal if not exists
        createNotificationsModal();
        
        // Load initial notification count
        notificationSystem.updateBadge();
    }

    if (user && user.is_admin) {
        const usersLink = document.getElementById('usersNavLink');
        if (usersLink) usersLink.style.display = '';
        const settingsLink = document.getElementById('settingsNavLink');
        if (settingsLink) settingsLink.style.display = '';
    }
}

// Notification modal functions
function createNotificationsModal() {
    if (document.getElementById('notificationsModal')) return;
    
    const modal = document.createElement('div');
    modal.id = 'notificationsModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal notifications-modal">
            <div class="modal-header">
                <h2>Уведомления</h2>
                <button class="modal-close" onclick="closeModal('notificationsModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="notifications-actions">
                    <button class="btn btn-secondary btn-sm" onclick="markAllNotificationsRead()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="9 11 12 14 22 4"/>
                            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                        </svg>
                        Прочитать все
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="deleteAllNotifications()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        Удалить все
                    </button>
                </div>
                <div class="notification-list-container" id="notificationListContainer">
                    <div class="notification-empty">Загрузка...</div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function openNotificationsModal() {
    openModal('notificationsModal');
    loadNotificationList();
}

async function loadNotificationList() {
    const list = document.getElementById('notificationListContainer');
    if (!list) return;
    
    try {
        const notifications = await api.getNotifications(false, 100);
        
        if (notifications.length === 0) {
            list.innerHTML = '<div class="notification-empty">Нет уведомлений</div>';
            return;
        }
        
        list.innerHTML = notifications.map(n => `
            <div class="notification-item ${n.is_read ? '' : 'unread'}" onclick="openNotification(${n.id}, ${n.project_id || 'null'}, ${n.task_id || 'null'})">
                <div class="notification-item-icon">
                    ${getNotificationIcon(n.notification_type)}
                </div>
                <div class="notification-item-content">
                    <div class="notification-item-title">${escapeHtml(n.title)}</div>
                    ${n.message ? `<div class="notification-item-message">${escapeHtml(n.message)}</div>` : ''}
                    <div class="notification-item-time">${formatDateTime(n.created_at)}</div>
                </div>
                <button class="notification-item-delete" onclick="deleteNotificationItem(event, ${n.id})" title="Удалить">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<div class="notification-empty">Ошибка загрузки</div>';
    }
}

function getNotificationIcon(type) {
    const icons = {
        'task_updated': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>',
        'comment_added': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
        'attachment_added': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>',
        'stage_changed': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>',
        'task_assigned': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/></svg>'
    };
    return icons[type] || icons['task_updated'];
}

async function openNotification(notificationId, projectId, taskId) {
    try {
        await api.markNotificationAsRead(notificationId);
        notificationSystem.updateBadge();
    } catch (e) {}
    
    closeModal('notificationsModal');
    
    if (projectId && taskId) {
        window.location.href = `/project/${projectId}?task=${taskId}`;
    }
}

async function deleteNotificationItem(event, notificationId) {
    event.stopPropagation();
    try {
        await api.deleteNotification(notificationId);
        loadNotificationList();
        notificationSystem.updateBadge();
    } catch (e) {
        showAlert('Ошибка удаления уведомления');
    }
}

async function markAllNotificationsRead() {
    try {
        await api.markAllNotificationsAsRead();
        loadNotificationList();
        notificationSystem.updateBadge();
        showAlert('Все уведомления отмечены как прочитанные', 'success');
    } catch (e) {
        showAlert('Ошибка');
    }
}

async function deleteAllNotifications() {
    if (!confirm('Удалить все уведомления?')) return;
    
    try {
        await api.deleteAllNotifications();
        loadNotificationList();
        notificationSystem.updateBadge();
        showAlert('Все уведомления удалены', 'success');
    } catch (e) {
        showAlert('Ошибка удаления');
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Check auth on protected pages
function checkAuth() {
    if (!auth.isLoggedIn()) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

// Notification System
const notificationSystem = {
    lastNotificationId: 0,
    pollInterval: null,
    notificationSound: null,
    
    init() {
        // Create notification sound using Web Audio API
        this.createNotificationSound();
        
        // Create notification container
        if (!document.getElementById('notification-toast-container')) {
            const container = document.createElement('div');
            container.id = 'notification-toast-container';
            container.style.cssText = `
                position: fixed;
                top: 1rem;
                right: 1rem;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                max-width: 400px;
                pointer-events: none;
            `;
            document.body.appendChild(container);
        }
        
        // Start polling for new notifications
        this.startPolling();
    },
    
    createNotificationSound() {
        // Create a pleasant notification sound using Web Audio API
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.audioContext = audioContext;
        } catch (e) {
            console.log('Web Audio API not supported');
        }
    },
    
    playSound() {
        if (!this.audioContext) return;
        
        try {
            // Resume audio context if suspended (browser policy)
            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume();
            }
            
            const ctx = this.audioContext;
            const now = ctx.currentTime;
            
            // Create a pleasant two-tone notification sound
            const oscillator1 = ctx.createOscillator();
            const oscillator2 = ctx.createOscillator();
            const gainNode = ctx.createGain();
            
            oscillator1.connect(gainNode);
            oscillator2.connect(gainNode);
            gainNode.connect(ctx.destination);
            
            // First tone
            oscillator1.frequency.setValueAtTime(880, now); // A5
            oscillator1.type = 'sine';
            
            // Second tone (harmony)
            oscillator2.frequency.setValueAtTime(1108.73, now); // C#6
            oscillator2.type = 'sine';
            
            // Volume envelope
            gainNode.gain.setValueAtTime(0, now);
            gainNode.gain.linearRampToValueAtTime(0.15, now + 0.02);
            gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
            
            oscillator1.start(now);
            oscillator2.start(now);
            oscillator1.stop(now + 0.3);
            oscillator2.stop(now + 0.3);
        } catch (e) {
            console.log('Error playing notification sound:', e);
        }
    },
    
    async startPolling() {
        if (!auth.isLoggedIn()) return;
        
        // Initial fetch to get the latest notification ID
        try {
            const notifications = await api.getNotifications(true, 1);
            if (notifications.length > 0) {
                this.lastNotificationId = notifications[0].id;
            }
        } catch (e) {
            console.log('Error fetching initial notifications:', e);
        }
        
        // Poll every 10 seconds
        this.pollInterval = setInterval(() => this.checkNewNotifications(), 10000);
    },
    
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },
    
    async checkNewNotifications() {
        if (!auth.isLoggedIn()) {
            this.stopPolling();
            return;
        }
        
        try {
            const notifications = await api.getNotifications(true, 10);
            
            // Find new notifications
            const newNotifications = notifications.filter(n => n.id > this.lastNotificationId);
            
            if (newNotifications.length > 0) {
                // Update last notification ID
                this.lastNotificationId = Math.max(...newNotifications.map(n => n.id));
                
                // Show toast for each new notification
                newNotifications.reverse().forEach((n, index) => {
                    setTimeout(() => {
                        this.showToast(n);
                    }, index * 300);
                });
                
                // Play sound once for all new notifications
                this.playSound();
                
                // Update notification badge if exists
                this.updateBadge();
            }
        } catch (e) {
            console.log('Error checking notifications:', e);
        }
    },
    
    showToast(notification) {
        const container = document.getElementById('notification-toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = 'notification-toast';
        toast.style.cssText = `
            background: var(--bg-card, #1e1e2e);
            border: 1px solid var(--border-color, #313244);
            border-left: 4px solid var(--primary, #89b4fa);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            pointer-events: auto;
            cursor: pointer;
            transform: translateX(120%);
            transition: transform 0.3s ease, opacity 0.3s ease;
            opacity: 0;
        `;
        
        const iconMap = {
            'task_updated': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>',
            'comment_added': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
            'attachment_added': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>',
            'stage_changed': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>',
            'task_assigned': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/></svg>'
        };
        
        const icon = iconMap[notification.notification_type] || iconMap['task_updated'];
        
        toast.innerHTML = `
            <div style="display: flex; gap: 0.75rem; align-items: flex-start;">
                <div style="color: var(--primary, #89b4fa); flex-shrink: 0;">
                    ${icon}
                </div>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 600; color: var(--text-primary, #cdd6f4); margin-bottom: 0.25rem;">
                        ${this.escapeHtml(notification.title)}
                    </div>
                    ${notification.message ? `<div style="font-size: 0.875rem; color: var(--text-secondary, #a6adc8); line-height: 1.4;">${this.escapeHtml(notification.message)}</div>` : ''}
                    ${notification.task_title ? `<div style="font-size: 0.75rem; color: var(--text-tertiary, #6c7086); margin-top: 0.25rem;">📋 ${this.escapeHtml(notification.task_title)}</div>` : ''}
                </div>
                <button onclick="event.stopPropagation(); this.parentElement.parentElement.remove();" style="background: none; border: none; color: var(--text-secondary, #a6adc8); cursor: pointer; padding: 0; flex-shrink: 0;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `;
        
        // Click handler to navigate to task
        toast.addEventListener('click', async () => {
            // Mark as read
            try {
                await api.markNotificationAsRead(notification.id);
            } catch (e) {}
            
            // Navigate to task if available
            if (notification.project_id && notification.task_id) {
                window.location.href = `/project/${notification.project_id}?task=${notification.task_id}`;
            }
            
            toast.remove();
        });
        
        container.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(0)';
            toast.style.opacity = '1';
        });
        
        // Auto remove after 8 seconds
        setTimeout(() => {
            toast.style.transform = 'translateX(120%)';
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 8000);
    },
    
    async updateBadge() {
        try {
            const result = await api.getUnreadNotificationsCount();
            const badges = document.querySelectorAll('.notification-badge');
            badges.forEach(badge => {
                if (result.count > 0) {
                    badge.textContent = result.count > 99 ? '99+' : result.count;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            });
        } catch (e) {}
    },
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if on protected page
    const publicPages = ['/login', '/register'];
    const currentPath = window.location.pathname;
    
    if (!publicPages.includes(currentPath)) {
        if (checkAuth()) {
            updateNavbar();
            // Initialize notification system
            notificationSystem.init();
        }
    }
});

