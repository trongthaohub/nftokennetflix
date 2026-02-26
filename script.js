// DOM Elements
const cookieInput = document.getElementById('cookie-input');
const loadFileBtn = document.getElementById('load-file-btn');
const pasteBtn = document.getElementById('paste-btn');
const clearBtn = document.getElementById('clear-btn');
const generateBtn = document.getElementById('generate-btn');
const status = document.getElementById('status');
const results = document.getElementById('results');
const copyResultsBtn = document.getElementById('copy-results-btn');
const modeOptions = document.querySelectorAll('.mode-option');
const navTabs = document.querySelectorAll('.nav-tab');
const tabContents = document.querySelectorAll('.tab-content');
const batchFiles = document.getElementById('batch-files');
const fileList = document.getElementById('file-list');
const processBatchBtn = document.getElementById('process-batch-btn');
const batchStatus = document.getElementById('batch-status');
const batchResults = document.getElementById('batch-results');
const saveResultsBtn = document.getElementById('save-results-btn');
const totalFiles = document.getElementById('total-files');
const validFiles = document.getElementById('valid-files');
const invalidFiles = document.getElementById('invalid-files');
const notification = document.getElementById('notification');
const progressPercent = document.getElementById('progress-percent');
const progressFill = document.getElementById('progress');
const batchProgressFill = document.getElementById('batch-progress');

// Mobile Navigation Elements
const mobileBrowseBtn = document.getElementById('mobile-browse-btn');
const mobileMenu = document.getElementById('mobile-menu');
const mobileNavItems = document.querySelectorAll('.mobile-nav-item');

// Telegram Elements
const telegramToggle = document.getElementById('telegram-toggle');
const telegramConfig = document.getElementById('telegram-config');
const botTokenInput = document.getElementById('bot-token');
const chatIdInput = document.getElementById('chat-id');
const testTelegramBtn = document.getElementById('test-telegram-btn');
const telegramStatus = document.getElementById('telegram-status');

// Global variables
let currentMode = 'fullinfo';
let selectedFiles = [];
let batchResultsData = [];

// Event Listeners
document.addEventListener('DOMContentLoaded', initApp);
loadFileBtn.addEventListener('click', handleLoadFile);
pasteBtn.addEventListener('click', handlePaste);
clearBtn.addEventListener('click', handleClear);
generateBtn.addEventListener('click', handleGenerate);
copyResultsBtn.addEventListener('click', handleCopyResults);

modeOptions.forEach(option => {
    option.addEventListener('click', handleModeChange);
});

navTabs.forEach(tab => {
    tab.addEventListener('click', handleTabChange);
});

batchFiles.addEventListener('change', handleBatchFilesChange);
processBatchBtn.addEventListener('click', handleProcessBatch);
saveResultsBtn.addEventListener('click', handleSaveResults);
telegramToggle.addEventListener('change', updateTelegramUI);

// Mobile Nav listeners
if (mobileBrowseBtn) {
    mobileBrowseBtn.addEventListener('click', toggleMobileMenu);
}

mobileNavItems.forEach(item => {
    item.addEventListener('click', (e) => handleMobileTabChange(e));
});

// Close mobile menu when clicking outside
document.addEventListener('click', (e) => {
    if (mobileMenu && mobileMenu.classList.contains('active')) {
        if (!mobileMenu.contains(e.target) && e.target !== mobileBrowseBtn && !mobileBrowseBtn.contains(e.target)) {
            toggleMobileMenu();
        }
    }
});

// Initialize the application
function initApp() {
    updateFileList();
    loadTelegramConfig();
}

// Robust Copy Function
async function copyToClipboard(text) {
    if (!text) return false;

    // Try navigator.clipboard first
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Clipboard API failed', err);
        }
    }

    // Fallback to execCommand('copy')
    try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        return successful;
    } catch (err) {
        console.error('Fallback copy failed', err);
        return false;
    }
}

// Handle mode change
function handleModeChange(e) {
    const mode = e.target.dataset.mode;
    currentMode = mode;
    modeOptions.forEach(option => option.classList.remove('active'));
    e.target.classList.add('active');
}

// Handle tab change
function handleTabChange(e) {
    const target = e.currentTarget || e.target;
    const tabId = target.dataset.tab;
    if (!tabId) return;

    // Update Desktop Tabs
    navTabs.forEach(tab => tab.classList.remove('active'));
    tabContents.forEach(content => content.classList.remove('active'));

    const activeTab = Array.from(navTabs).find(t => t.dataset.tab === tabId);
    if (activeTab) activeTab.classList.add('active');

    // Update Mobile Tabs
    let activeText = 'Duyệt tìm';
    mobileNavItems.forEach(item => {
        if (item.dataset.tab === tabId) {
            item.classList.add('active');
            // Don't take text from helper links like Telegram support
            if (item.dataset.tab) activeText = item.textContent;
        } else {
            item.classList.remove('active');
        }
    });

    // Update Mobile Browse Label
    if (mobileBrowseBtn) {
        mobileBrowseBtn.innerHTML = `${activeText} <i class="fas fa-caret-down"></i>`;
    }

    document.getElementById(`${tabId}-tab`).classList.add('active');
}

function toggleMobileMenu() {
    mobileMenu.classList.toggle('active');
}

function handleMobileTabChange(e) {
    handleTabChange(e);
    toggleMobileMenu();
}

// Handle load file
function handleLoadFile() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.txt,.json,.zip';
    input.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = e => {
            cookieInput.value = e.target.result;
            showNotification('Đã tải tệp thành công');
        };
        reader.readAsText(file);
    };
    input.click();
}

// Handle paste from clipboard
async function handlePaste() {
    try {
        const text = await navigator.clipboard.readText();
        cookieInput.value = text;
        showNotification('Đã dán nội dung');
    } catch (err) {
        showNotification('Không thể truy cập bộ nhớ tạm', true);
    }
}

// Handle clear input
function handleClear() {
    cookieInput.value = '';
    showNotification('Đã xóa nội dung nhập');
}

// Handle generate token
async function handleGenerate() {
    const content = cookieInput.value.trim();
    if (!content) {
        showNotification('Vui lòng nhập nội dung trước', true);
        return;
    }

    generateBtn.disabled = true;
    generateBtn.innerHTML = '<div class="spinner"></div>';
    progressFill.style.width = '0%';
    if (progressPercent) progressPercent.textContent = '0%';
    status.textContent = 'Đang xử lý...';

    try {
        const response = await fetch('/api/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content, mode: currentMode })
        });

        const data = await response.json();

        if (data.status === 'success') {
            progressFill.style.width = '100%';
            if (progressPercent) progressPercent.textContent = '100%';
            status.textContent = 'Xong';
            displayResults(data);
            showNotification('Thành công');
        } else {
            progressFill.style.width = '100%';
            if (progressPercent) progressPercent.textContent = '100%';
            status.textContent = 'Lỗi';
            displayError(data.message);
            showNotification(data.message, true);
        }
    } catch (error) {
        progressFill.style.width = '100%';
        if (progressPercent) progressPercent.textContent = '100%';
        status.textContent = 'Lỗi mạng';
        displayError('Lỗi mạng: ' + error.message);
        showNotification('Lỗi mạng: ' + error.message, true);
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = 'KIỂM TRA NGAY';
    }
}

// Handle copy results
async function handleCopyResults() {
    const textToCopy = results.innerText;
    const success = await copyToClipboard(textToCopy);
    if (success) {
        showNotification('Đã sao chép kết quả');
    } else {
        showNotification('Lỗi khi sao chép', true);
    }
}

// Handle batch files change
function handleBatchFilesChange(e) {
    selectedFiles = Array.from(e.target.files);
    updateFileList();
}

// Update file list display
function updateFileList() {
    fileList.innerHTML = '';
    if (selectedFiles.length === 0) {
        fileList.innerHTML = '<div class="empty-list-text">Chưa chọn tệp nào</div>';
        return;
    }
    selectedFiles.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-row';
        fileItem.innerHTML = `<span>${file.name}</span><span class="tag">Chờ xử lý</span>`;
        fileList.appendChild(fileItem);
    });
    totalFiles.textContent = selectedFiles.length;
}

// Handle process batch
async function handleProcessBatch() {
    if (selectedFiles.length === 0) {
        showNotification('Vui lòng chọn tệp trước', true);
        return;
    }

    batchResultsData = [];
    batchResults.innerHTML = '';
    saveResultsBtn.disabled = true;
    processBatchBtn.disabled = true;
    processBatchBtn.innerHTML = '<div class="spinner"></div>';
    batchProgressFill.style.width = '0%';
    batchStatus.textContent = 'Đang xử lý...';

    const formData = new FormData();
    selectedFiles.forEach(file => formData.append('files', file));
    formData.append('mode', currentMode);

    try {
        const response = await fetch('/api/batch-check', { method: 'POST', body: formData });
        const data = await response.json();

        if (data.status === 'success') {
            batchResultsData = data.results;
            displayBatchResults(batchResultsData);
            batchProgressFill.style.width = '100%';
            batchStatus.textContent = 'Hoàn tất';
            saveResultsBtn.disabled = false;
            const valid = batchResultsData.filter(r => r.status === 'success').length;
            showNotification(`Xử lý hoàn tất: ${valid} hợp lệ`);
        } else {
            batchProgressFill.style.width = '100%';
            batchStatus.textContent = 'Lỗi';
            showNotification(data.message, true);
        }
    } catch (error) {
        batchProgressFill.style.width = '100%';
        batchStatus.textContent = 'Lỗi mạng';
        showNotification('Lỗi mạng: ' + error.message, true);
    } finally {
        processBatchBtn.disabled = false;
        processBatchBtn.innerHTML = 'BẮT ĐẦU XỬ LÝ';
    }
}

// Display batch results
function displayBatchResults(results) {
    batchResults.innerHTML = '';
    let validCount = 0;
    let invalidCount = 0;

    results.forEach(result => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-row';
        if (result.status === 'success') {
            fileItem.innerHTML = `<span>${result.filename} (${result.account_info.country})</span><span class="tag success">Hợp lệ</span>`;
            validCount++;
        } else {
            fileItem.innerHTML = `<span>${result.filename}</span><span class="tag error">Lỗi</span>`;
            invalidCount++;
        }
        batchResults.appendChild(fileItem);
    });

    validFiles.textContent = validCount;
    invalidFiles.textContent = invalidCount;
}

// Handle save results
function handleSaveResults() {
    if (batchResultsData.length === 0) return;
    let content = 'Netflix Cookies Checker - Kết Quả Hàng Loạt\n\n';
    batchResultsData.forEach(result => {
        if (result.status === 'success') {
            const acc = result.account_info;
            content += `✅ ${result.filename} | ${acc.email} | ${acc.plan} | ${acc.country}\n`;
            if (result.token_result.status === 'Success') {
                content += `Token: ${result.token_result.token}\nLink: ${result.token_result.direct_login_url}\n`;
            }
        } else {
            content += `❌ ${result.filename}: ${result.message}\n`;
        }
        content += '─'.repeat(50) + '\n';
    });

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `results_${new Date().getTime()}.txt`;
    a.click();
}

// Display results in UI
function displayResults(data) {
    let html = '';
    if (currentMode === 'fullinfo') {
        const acc = data.account_info;
        html += `
            <div class="result-block">
                <div class="result-block-header">TỔNG QUAN TÀI KHOẢN <span class="tag success">Hợp lệ</span></div>
                <div class="result-block-content">
                    <div class="info-row"><span class="info-label">Gói cước:</span><span class="info-value">${acc.plan}</span></div>
                    <div class="info-row"><span class="info-label">Quốc gia:</span><span class="info-value">${acc.country}</span></div>
                    <div class="info-row"><span class="info-label">Video:</span><span class="info-value">${acc.video_quality}</span></div>
                    <div class="info-row"><span class="info-label">Email:</span><span class="info-value">${acc.email.replace(/\\x40/g, '@')}</span></div>
                    <div class="info-row"><span class="info-label">Gia hạn:</span><span class="info-value">${acc.next_billing}</span></div>
                </div>
            </div>`;
    }

    const token = data.token_result;
    if (token.status === 'Success') {
        const expTime = new Date(token.expires * 1000).toLocaleString();
        html += `
            <div class="result-block">
                <div class="result-block-header">THÔNG TIN TOKEN</div>
                <div class="result-block-content">
                    <div class="token-area">
                        <div class="info-row"><span class="info-label">Hết hạn:</span><span class="info-value">${expTime}</span></div>
                        
                        <p class="info-label" style="margin-top:15px">Link Đăng Nhập:</p>
                        <div class="token-box" id="token-url-text">${token.direct_login_url}</div>
                        <button class="copy-token-btn" id="copy-link-btn">Sao chép Link</button>
                        
                        <p class="info-label" style="margin-top:15px">Mã Token:</p>
                        <div class="token-box" id="token-code-text">${token.token}</div>
                        <button class="copy-token-btn" id="copy-token-btn">Sao chép Token</button>
                    </div>
                </div>
            </div>`;
    } else {
        html += `
            <div class="result-block">
                <div class="result-block-header">LỖI TẠO TOKEN <span class="tag error">Lỗi</span></div>
                <div class="result-block-content"><p>${token.error}</p></div>
            </div>`;
    }

    results.innerHTML = html;
    copyResultsBtn.disabled = false;

    // Attach listeners to new buttons
    const copyLinkBtn = document.getElementById('copy-link-btn');
    const copyTokenBtn = document.getElementById('copy-token-btn');

    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', () => {
            copyToClipboard(token.direct_login_url).then(success => {
                if (success) showNotification('Đã sao chép link');
            });
        });
    }

    if (copyTokenBtn) {
        copyTokenBtn.addEventListener('click', () => {
            copyToClipboard(token.token).then(success => {
                if (success) showNotification('Đã sao chép token');
            });
        });
    }
}

function displayError(message) {
    results.innerHTML = `<div class="result-block"><div class="result-block-header" style="color:var(--netflix-red)">LỖI HỆ THỐNG</div><div class="result-block-content">${message}</div></div>`;
    copyResultsBtn.disabled = true;
}

function showNotification(message, isError = false) {
    notification.textContent = message;
    notification.style.color = isError ? 'var(--netflix-red)' : 'black';
    notification.classList.add('show');
    setTimeout(() => notification.classList.remove('show'), 3000);
}

// Telegram Config
function loadTelegramConfig() {
    const saved = localStorage.getItem('telegramConfig');
    if (saved) {
        const config = JSON.parse(saved);
        telegramToggle.checked = config.enabled || false;
        botTokenInput.value = config.bot_token || '';
        chatIdInput.value = config.chat_id || '';
    }
    updateTelegramUI();
}

function updateTelegramUI() {
    if (telegramToggle.checked) {
        telegramConfig.classList.remove('hide');
        telegramStatus.innerText = 'Telegram: Đang bật';
    } else {
        telegramConfig.classList.add('hide');
        telegramStatus.innerText = 'Telegram: Tắt';
    }
    saveTelegramConfig();
}

function saveTelegramConfig() {
    const config = {
        enabled: telegramToggle.checked,
        bot_token: botTokenInput.value,
        chat_id: chatIdInput.value
    };
    localStorage.setItem('telegramConfig', JSON.stringify(config));
}

async function testTelegramConnection() {
    if (!botTokenInput.value || !chatIdInput.value) {
        showNotification('Vui lòng nhập Bot Token và Chat ID', true);
        return;
    }
    testTelegramBtn.disabled = true;
    testTelegramBtn.innerHTML = '<i class="fas fa-sync fa-spin"></i>';
    showNotification('Đang gửi test...');

    try {
        const response = await fetch(`https://api.telegram.org/bot${botTokenInput.value}/sendMessage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: chatIdInput.value,
                text: '✅ Netflix Tools Test OK!',
                parse_mode: 'Markdown'
            })
        });
        const data = await response.json();
        if (data.ok) showNotification('Gửi thành công!');
        else showNotification('Lỗi: ' + data.description, true);
    } catch (err) {
        showNotification('Lỗi kết nối', true);
    } finally {
        testTelegramBtn.disabled = false;
        testTelegramBtn.innerHTML = 'Test';
    }
}

testTelegramBtn.addEventListener('click', testTelegramConnection);
botTokenInput.addEventListener('input', saveTelegramConfig);
chatIdInput.addEventListener('input', saveTelegramConfig);
function dabiluxNuoiThanToggle() {
    const widget = document.getElementById('dabilux-nuoi-than-widget');
    if (widget) {
        widget.classList.toggle('active');
    }
}