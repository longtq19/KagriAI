// Configuration
const __params = new URLSearchParams(window.location.search);
// const WS_URL = __params.get('ws') || 'ws://localhost:8000/ws/chat';
// const TTS_URL_BASE = __params.get('tts') || 'http://localhost:5050';

const WS_URL = __params.get('ws') || 'ws://192.168.88.111:8000/ws/kagriai';
console.log('Connecting to WebSocket:', WS_URL);
// const MODEL_URL = __params.get('model') || 'http://localhost:8000/models/durain/model.json';
// const META_URL = __params.get('meta') || 'http://localhost:8000/models/durain/metadata.json';

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const imageUpload = document.getElementById('image-upload');
const imagePreview = document.getElementById('image-preview');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const suggestionsContainer = document.getElementById('suggestions');
// const selectionModal = document.getElementById('selection-modal'); // Removed
const confirmModal = document.getElementById('confirm-modal');
const treeModal = document.getElementById('tree-modal');
const btnOpenDiagnose = document.getElementById('btn-open-diagnose');
const btnConfirmAgree = document.getElementById('btn-confirm-agree');
const btnConfirmCancel = document.getElementById('btn-confirm-cancel');
// const btnDiagnose = document.getElementById('btn-diagnose'); // Removed
// const btnIncorrect = document.getElementById('btn-incorrect'); // Removed

// State
let ws = null;
let conversationId = null; // Removed random ID generation
let currentImageBase64 = null;
let isDiagnosisMode = false;
let isGenerating = false;
const BACKEND_URL = __params.get('backend') || 'http://192.168.88.111:8000';
let currentBotMessageDiv = null;
let currentBotMessageContent = "";
let typingQueue = [];
let isTyping = false;
let typingTimer = null;
let pendingOutbox = [];
let currentPredictedLabel = null;

// Initialize
async function loadClientIdConfig() {
    let saved = null;
    try {
        saved = localStorage.getItem('client_id');
    } catch (e) {
        saved = null;
    }
    if (!saved || typeof saved !== 'string' || !saved.trim()) {
        let entered = '';
        const canPrompt = typeof window.prompt === 'function';
        if (canPrompt) {
            try {
                while (!entered) {
                    entered = window.prompt('Nhập ID khách hàng để bắt đầu:', '') || '';
                    entered = entered.trim();
                    if (!entered) {
                        alert('ID không được để trống. Vui lòng nhập lại.');
                    }
                }
            } catch (e) {
                entered = '';
            }
        }
        if (!entered) {
            entered = await new Promise((resolve) => {
                const overlay = document.createElement('div');
                overlay.style.position = 'fixed';
                overlay.style.inset = '0';
                overlay.style.background = 'rgba(0,0,0,0.4)';
                overlay.style.display = 'flex';
                overlay.style.alignItems = 'center';
                overlay.style.justifyContent = 'center';
                overlay.style.zIndex = '9999';
                const box = document.createElement('div');
                box.style.background = '#fff';
                box.style.padding = '16px';
                box.style.borderRadius = '8px';
                box.style.width = '90%';
                box.style.maxWidth = '420px';
                box.innerHTML = `
                    <h3 style="margin:0 0 8px 0;">Nhập ID khách hàng để bắt đầu</h3>
                    <input id="client-id-input" type="text" placeholder="VD: KH-123" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:6px;"/>
                    <div style="margin-top:12px;text-align:right;">
                        <button id="client-id-submit" style="padding:8px 12px;border:none;background:#2b7cff;color:#fff;border-radius:6px;cursor:pointer;">Xác nhận</button>
                    </div>
                `;
                overlay.appendChild(box);
                document.body.appendChild(overlay);
                box.querySelector('#client-id-submit').addEventListener('click', () => {
                    const val = box.querySelector('#client-id-input').value.trim();
                    if (!val) {
                        alert('ID không được để trống.');
                        return;
                    }
                    overlay.remove();
                    resolve(val);
                });
            });
        }
        try {
            localStorage.setItem('client_id', entered);
        } catch (e) {}
        saved = entered;
    }
    conversationId = saved.trim();
    console.log('Client ID:', conversationId);
}

async function init() {
    // Configure Marked.js for proper line breaks
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }

    await loadClientIdConfig();
    connectWebSocket();
    setupEventListeners();
    }

// Client-side TF model removed; backend handles diagnosis

// WebSocket Connection
function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        statusDot.className = 'dot connected';
        statusText.textContent = 'Đã kết nối';
        console.log('Connected to WebSocket');
        while (pendingOutbox.length > 0) {
            const d = pendingOutbox.shift();
            ws.send(d);
        }
    };

    ws.onclose = () => {
        statusDot.className = 'dot disconnected';
        statusText.textContent = 'Mất kết nối';
        console.log('Disconnected. Reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket Error:', error);
        console.error('WebSocket URL:', WS_URL);
        console.error('ReadyState:', ws.readyState);
        isGenerating = false;
        updateSendButtonState();
        // Attempt reconnect; onclose handler will kick in
        try { ws.close(); } catch (e) {}
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleResponse(data);
    };
}

// Event Listeners
function setupEventListeners() {
    // Send Message
    sendBtn.addEventListener('click', () => sendMessage());
    
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize Textarea
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value === '') this.style.height = 'auto';
    });

    // Image Upload
    imageUpload.addEventListener('change', handleImageUpload);

    // Diagnosis Flow
    if (btnOpenDiagnose) btnOpenDiagnose.addEventListener('click', () => {
        confirmModal.style.display = 'flex';
    });

    if (btnConfirmAgree) btnConfirmAgree.addEventListener('click', () => {
        confirmModal.style.display = 'none';
        isDiagnosisMode = true;
        imageUpload.click();
    });

    if (btnConfirmCancel) btnConfirmCancel.addEventListener('click', () => {
        confirmModal.style.display = 'none';
        isDiagnosisMode = false;
    });
}

// Handle Image Upload
function handleImageUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        currentImageBase64 = e.target.result;
        imagePreview.innerHTML = `
            <div class="preview-item">
                <img src="${currentImageBase64}" alt="Preview">
                <button class="remove-btn" onclick="removeImage()">×</button>
            </div>
        `;
        // Predict client side label if needed, but we rely on backend now for diagnosis
        // predictLabel(currentImageBase64).then(l => { currentPredictedLabel = l; }).catch(() => { currentPredictedLabel = null; });
    };
    reader.readAsDataURL(file);
    imageUpload.value = '';
}

// Remove Image
window.removeImage = function() {
    currentImageBase64 = null;
    imagePreview.innerHTML = '';
    isDiagnosisMode = false; // Reset mode if image is removed
};

// Send Message
function sendMessage(text = null) {
    if (isGenerating) return;

    const content = text || messageInput.value.trim();
    if (!content && !currentImageBase64) return;
    
    // Check if in diagnosis mode with image
    if (currentImageBase64 && isDiagnosisMode) {
        // Show Tree Selection
        treeModal.style.display = 'flex';
        return;
    }
    
    processMessageSend(content, currentImageBase64);
}

// Tree Selection Logic
window.selectTree = function(treeType) {
    treeModal.style.display = 'none';
    diagnoseDisease(treeType);
}

window.closeTreeModal = function() {
    treeModal.style.display = 'none';
}

async function diagnoseDisease(treeType) {
    // Show loading state
    isGenerating = true;
    updateSendButtonState();
    
    // Add User Message with Image
    const content = messageInput.value.trim();
    addMessage(content || ("Chẩn đoán bệnh cho cây " + (treeType === 'durian' ? 'Sầu Riêng' : 'Cà Phê')), 'user', currentImageBase64);
    
    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    const loadingMsg = addMessage("", 'bot');
    loadingMsg.querySelector('.message-content').innerHTML = '<div class="typing-indicator">...</div>';
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/diagnose/${treeType}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: currentImageBase64, session_id: conversationId, text: content })
        });
        
        const result = await response.json();
        
        // Render Result
        renderDiagnosisResult(loadingMsg, result);
        
    } catch (e) {
        loadingMsg.querySelector('.message-content').textContent = "Lỗi kết nối server: " + e.message;
    } finally {
        isGenerating = false;
        updateSendButtonState();
        removeImage(); // This resets isDiagnosisMode
    }
}

function renderDiagnosisResult(msgDiv, result) {
    const contentDiv = msgDiv.querySelector('.message-content');
    if (result.error) {
        contentDiv.textContent = "Lỗi: " + result.error;
        return;
    }
    
    let html = `<p><strong>Kết quả chẩn đoán:</strong></p>`;
    if (result.predictions && result.predictions.length > 0) {
        result.predictions.forEach(p => {
            html += `
            <div class="diagnosis-item">
                <div class="diagnosis-header">
                    <span class="diagnosis-name">${p.name}</span>
                    <span class="diagnosis-prob">${p.probability}%</span>
                </div>
                <div class="diagnosis-images">
                    ${p.images.map(url => `<img src="${BACKEND_URL}${url}" class="diagnosis-img" onclick="window.open(this.src, '_blank')">`).join('')}
                </div>
            </div>`;
        });
    } else {
        html += "<p>Không tìm thấy bệnh phù hợp hoặc cây khỏe mạnh.</p>";
    }
    contentDiv.innerHTML = html;
    scrollToBottom();
}

function updateSendButtonState() {
    if (isGenerating) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    } else {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
    }
}

/* Old functions removed */

function processMessageSend(content, imageToSend) {
    // Remove suggestions if visible
    if (suggestionsContainer) {
        suggestionsContainer.style.display = 'none';
    }

    // Add User Message
    addMessage(content, 'user', imageToSend);
    
    // Clear Input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Prepare Bot Message Placeholder BEFORE sending to handle early progress packets
    isGenerating = true;
    updateSendButtonState();
    isStreamFinished = false; // Reset stream status
    currentBotMessageContent = "";
    typingQueue = [];
    // syncQueue = []; // Was not defined in original file, removing to avoid error if strict mode
    if (typingTimer) clearTimeout(typingTimer);
    isTyping = false;
    
    currentBotMessageDiv = addMessage("", 'bot'); // Empty initially
    
    // Waiting state removed
    
    // Prepare Payload and send
    if (imageToSend) {
        const payload = {
            id: conversationId,
            type: "image_query",
            text: content || "",
            image_base64: imageToSend,
            client_label: currentPredictedLabel
        };
        const msg = JSON.stringify(payload);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(msg);
        } else {
            pendingOutbox.push(msg);
        }
    } else {
        const payload = {
            id: conversationId,
            type: "text",
            text: content
        };
        const msg = JSON.stringify(payload);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(msg);
        } else {
            pendingOutbox.push(msg);
        }
    }
    removeImage();
}

// Add Message to UI
function addMessage(text, role, image = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    let contentHtml = '';
    
    if (image) {
        contentHtml += `<div class="message-image"><img src="${image}" style="max-width: 200px; border-radius: 8px; margin-bottom: 8px;"></div>`;
    }
    
    if (role === 'user') {
        contentHtml += text.replace(/\n/g, '<br>');
    } else {
        // Bot message (initially empty or formatted markdown)
        contentHtml += text ? marked.parse(text) : '';
    }

    msgDiv.innerHTML = `
        <div class="message-content">
            ${contentHtml}
        </div>
    `;

    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
}

// Handle WebSocket Response
function handleResponse(data) {
    if (!currentBotMessageDiv) return;

    const contentDiv = currentBotMessageDiv.querySelector('.message-content');

    if (data.type === 'stream') {
        // Ensure typing area exists; keep any progress list
        const typingIcon = contentDiv.querySelector('.typing-indicator');
        if (typingIcon) typingIcon.remove();
        let answerDiv = contentDiv.querySelector('.final-answer');
        if (!answerDiv) {
            answerDiv = document.createElement('div');
            answerDiv.className = 'final-answer';
            contentDiv.appendChild(answerDiv);
        }
        
        // Push characters to queue
        const chars = data.content.split('');
        typingQueue.push(...chars);
        // Start typing if not already
        if (!isTyping) {
            processTypingQueue();
        }
    } 
    else if (data.type === 'start') {
        // No-op
    }
    else if (data.type === 'end') {
        isStreamFinished = true;
        // Allow user to send tiếp ngay sau khi luồng kết thúc
        isGenerating = false;
        updateSendButtonState();
        // Mark last progress step as done and stop spinner
        const steps = contentDiv.querySelector('.progress-steps');
        if (steps) {
            const last = steps.lastElementChild;
            if (last && !last.classList.contains('done')) {
                last.classList.add('done');
                const icon = last.querySelector('i');
                if (icon) {
                    icon.classList.remove('fa-spinner','fa-spin');
                    icon.classList.add('fa-check');
                }
            }
        }
        // Push end signal
        typingQueue.push(null);
        if (!isTyping) processTypingQueue();
    }
    else if (data.type === 'error') {
        contentDiv.innerHTML += `<br><span style="color: red;">Error: ${data.content}</span>`;
        isGenerating = false;
        updateSendButtonState();
        typingQueue = [];
    }
    else if (data.type === 'progress') {
        // Show step-by-step progress to reduce impatience
        const typingIcon = contentDiv.querySelector('.typing-indicator');
        if (typingIcon) typingIcon.remove();
        let steps = contentDiv.querySelector('.progress-steps');
        if (!steps) {
            steps = document.createElement('div');
            steps.className = 'progress-steps';
            contentDiv.appendChild(steps);
        }
        const last = steps.lastElementChild;
        if (last && !last.classList.contains('done')) {
            last.classList.add('done');
            const icon = last.querySelector('i');
            if (icon) {
                icon.classList.remove('fa-spinner','fa-spin');
                icon.classList.add('fa-check');
            }
        }
        const step = document.createElement('div');
        step.className = 'progress-step';
        step.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${data.text || 'Đang xử lý...'}`;
        steps.appendChild(step);
    }
}

// Process Typing Queue
function processTypingQueue() {
    if (typingQueue.length > 0) {
        isTyping = true;
        
        // Speed adjustment: if queue is long, speed up to catch up
        // Normal Vietnamese reading speed ~300 wpm -> ~25 chars/sec -> 40ms/char
        const delay = typingQueue.length > 50 ? 5 : 40;
        
        const char = typingQueue.shift();
        
        if (char === null) {
            // End of stream signal
            isGenerating = false;
            isTyping = false;
            currentBotMessageDiv = null;
            return;
        }
        
        currentBotMessageContent += char;
        
        // Update UI
        if (currentBotMessageDiv) {
            const contentDiv = currentBotMessageDiv.querySelector('.message-content');
            // Re-render Markdown
            const answerDiv = contentDiv.querySelector('.final-answer') || contentDiv;
            answerDiv.innerHTML = marked.parse(currentBotMessageContent);
            scrollToBottom();
        }
        
        typingTimer = setTimeout(processTypingQueue, delay);
    } else {
        isTyping = false;
    }
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Quick Suggestion
window.sendSuggestion = function(text) {
    messageInput.value = text;
    messageInput.focus();
    // Trigger resize
    messageInput.dispatchEvent(new Event('input'));
};

// Clear Chat
window.clearChat = function() {
    chatMessages.innerHTML = '';
    // Re-add Welcome
    chatMessages.innerHTML = `
        <div class="message bot welcome-message">
            <div class="message-content">
                <p>Xin chào! Tôi là <strong>Kagri AI</strong>.</p>
                <p>Tôi có thể giúp bạn tra cứu thông tin sản phẩm, kỹ thuật canh tác và giải đáp thắc mắc về nông nghiệp.</p>
            </div>
        </div>
    `;
    // Re-add Suggestions
    if (suggestionsContainer) {
        suggestionsContainer.style.display = 'flex';
        chatMessages.appendChild(suggestionsContainer);
    }
};

// Init on load
console.log("App starting...");
init();
