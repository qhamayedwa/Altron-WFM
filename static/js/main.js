// Main JavaScript for Flask PostgreSQL App

// Database status checker
class DatabaseStatus {
    constructor() {
        this.statusIndicator = document.getElementById('db-status');
        this.statusText = document.getElementById('db-status-text');
        this.init();
    }

    init() {
        if (this.statusIndicator) {
            this.checkStatus();
            // Check status every 30 seconds
            setInterval(() => this.checkStatus(), 30000);
        }
    }

    async checkStatus() {
        try {
            this.setStatus('loading', 'Checking...');
            
            const response = await fetch('/api/v1/db-status');
            const data = await response.json();
            
            if (response.ok && data.status === 'connected') {
                this.setStatus('connected', 'Connected');
                this.updateTableCounts(data.tables);
            } else {
                this.setStatus('error', 'Error');
                console.error('Database status error:', data.message);
            }
        } catch (error) {
            this.setStatus('error', 'Error');
            console.error('Failed to check database status:', error);
        }
    }

    setStatus(status, text) {
        if (this.statusIndicator) {
            this.statusIndicator.className = `db-status ${status}`;
        }
        if (this.statusText) {
            this.statusText.textContent = text;
        }
    }

    updateTableCounts(tables) {
        // Update count displays if they exist
        Object.entries(tables).forEach(([table, count]) => {
            const element = document.getElementById(`${table}-count`);
            if (element) {
                element.textContent = count;
            }
        });
    }
}

// Flash message handler
class FlashMessages {
    constructor() {
        this.init();
    }

    init() {
        // Auto-dismiss flash messages after 5 seconds
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            setTimeout(() => {
                const bsAlert = new bootstrap.Alert(alert);
                if (bsAlert) {
                    bsAlert.close();
                }
            }, 5000);
        });
    }

    show(message, type = 'info') {
        const alertContainer = document.getElementById('flash-messages');
        if (!alertContainer) return;

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        alertContainer.appendChild(alertDiv);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertDiv);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    }
}

// Sample data creator
class SampleDataManager {
    constructor() {
        this.button = document.getElementById('create-sample-data');
        this.init();
    }

    init() {
        if (this.button) {
            this.button.addEventListener('click', (e) => {
                e.preventDefault();
                this.createSampleData();
            });
        }
    }

    async createSampleData() {
        try {
            this.button.disabled = true;
            this.button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';

            const response = await fetch('/create-sample-data');
            const data = await response.json();

            if (response.ok) {
                flashMessages.show(data.message, 'success');
                // Refresh page after 2 seconds to show new data
                setTimeout(() => window.location.reload(), 2000);
            } else {
                flashMessages.show(data.message, 'danger');
            }
        } catch (error) {
            console.error('Error creating sample data:', error);
            flashMessages.show('Failed to create sample data', 'danger');
        } finally {
            this.button.disabled = false;
            this.button.innerHTML = 'Create Sample Data';
        }
    }
}

// Loading states for forms
class LoadingManager {
    static showLoading(element) {
        element.classList.add('loading');
        const buttons = element.querySelectorAll('button[type="submit"]');
        buttons.forEach(btn => {
            btn.disabled = true;
            const originalText = btn.textContent;
            btn.setAttribute('data-original-text', originalText);
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
        });
    }

    static hideLoading(element) {
        element.classList.remove('loading');
        const buttons = element.querySelectorAll('button[type="submit"]');
        buttons.forEach(btn => {
            btn.disabled = false;
            const originalText = btn.getAttribute('data-original-text');
            if (originalText) {
                btn.textContent = originalText;
            }
        });
    }
}

// Utility functions
const utils = {
    // Format date for display
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // Debounce function for search inputs
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Copy text to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Failed to copy text:', err);
            return false;
        }
    }
};

// Initialize components when DOM is loaded
let dbStatus, flashMessages, sampleDataManager;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    dbStatus = new DatabaseStatus();
    flashMessages = new FlashMessages();
    sampleDataManager = new SampleDataManager();

    // Add fade-in animation to main content
    const mainContent = document.querySelector('main');
    if (mainContent) {
        mainContent.classList.add('fade-in');
    }

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
});

// Global error handler
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
});
