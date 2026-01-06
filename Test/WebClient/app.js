// Configuration
const __params = new URLSearchParams(window.location.search);
// const WS_URL = __params.get('ws') || 'ws://localhost:8000/ws/chat';
// const TTS_URL_BASE = __params.get('tts') || 'http://localhost:5050';

const WS_URL = __params.get('ws') || 'ws://127.0.0.1:8001/ws/kagri-ai';
console.log('Connecting to WebSocket:', WS_URL);
const TTS_URL_BASE = __params.get('tts') || 'http://127.0.0.1:5500';
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
let conversationId = 'user_' + Math.random().toString(36).substr(2, 9);
let currentImageBase64 = null;
let isDiagnosisMode = false;
let isGenerating = false;
const BACKEND_URL = "http://localhost:8001"; // Define backend URL
let currentBotMessageDiv = null;
let currentBotMessageContent = "";
let typingQueue = [];
let isTyping = false;
let typingTimer = null;
let isTTSEnabled = false; // TTS State
let ttsQueue = []; // Holds Promises of Audio/Blob
let isTTSPlaying = false;
let ttsBuffer = "";
let currentAudio = null; // Track currently playing audio
let pendingDisplayQueue = []; // Queue for text waiting for audio
let isStreamFinished = false; // Track if WebSocket stream has ended
let pendingOutbox = [];
let diseaseModel = null;
let modelLabels = [];
let currentPredictedLabel = null;
let responseTimer = null;

// Initialize
function toggleTTS() {
    isTTSEnabled = !isTTSEnabled;
    if (!isTTSEnabled) {
        ttsQueue = [];
        pendingDisplayQueue = [];
        isTTSPlaying = false;
        ttsBuffer = "";
        currentAudio = null;
    }
}

function init() {
    // Configure Marked.js for proper line breaks
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }

    connectWebSocket();
    setupEventListeners();
    loadDiseaseModel();
}

async function loadDiseaseModel() {
    try {
        const meta = await fetch(META_URL).then(r => r.json());
        if (Array.isArray(meta.labels)) modelLabels = meta.labels;
        diseaseModel = await tf.loadLayersModel(MODEL_URL);
    } catch (e) {
        diseaseModel = null;
    }
}

function dataUrlToImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = src;
    });
}

async function imageToTensor(dataUrl) {
    const img = await dataUrlToImage(dataUrl);
    const canvas = document.createElement('canvas');
    canvas.width = 224;
    canvas.height = 224;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, 224, 224);
    const t = tf.browser.fromPixels(canvas).toFloat().div(255.0).expandDims(0);
    return t;
}

async function predictLabel(dataUrl) {
    try {
        if (!diseaseModel) return null;
        const t = await imageToTensor(dataUrl);
        const logits = diseaseModel.predict(t);
        const arr = await logits.array();
        const v = arr[0];
        let maxIdx = 0;
        for (let i = 1; i < v.length; i++) if (v[i] > v[maxIdx]) maxIdx = i;
        const label = modelLabels[maxIdx] || null;
        tf.dispose([t, logits]);
        return label;
    } catch (e) {
        return null;
    }
}

// TTS Toggle Function
window.toggleTTS = function() {
    isTTSEnabled = !isTTSEnabled;
    const btn = document.getElementById('tts-toggle-btn');
    const icon = document.getElementById('tts-icon');
    
    if (isTTSEnabled) {
        btn.classList.add('active');
        icon.className = 'fas fa-volume-up';
        
        // Unlock Audio Context for Mobile/Autoplay Policy
        const unlockAudio = new Audio();
        unlockAudio.play().catch(e => {});

        // Check if Local TTS Server is reachable
        fetch(TTS_URL_BASE + '/')
            .then(res => {
                if(res.ok) console.log("Local TTS Server Connected (Edge-TTS)");
            })
            .catch(err => {
                console.warn("Local TTS Server unreachable. Will fallback to Browser TTS.");
                alert("⚠️ Lưu ý: Server giọng nói chất lượng cao chưa chạy.\nHãy chạy file 'run_tts.bat' để có giọng đọc tự nhiên nhất.\n\nHệ thống sẽ dùng giọng đọc mặc định của trình duyệt (chất lượng thấp hơn).");
            });
    } else {
        btn.classList.remove('active');
        icon.className = 'fas fa-volume-mute';
        
        // STOP TTS IMMEDIATELY
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        window.speechSynthesis.cancel();
        isTTSPlaying = false;
        ttsQueue = []; // Clear Promise Queue
        ttsBuffer = "";
        
        // FLUSH ALL PENDING TEXT IMMEDIATELY
        // Move everything from pendingDisplayQueue to typingQueue
        
        // 1. Text from pendingDisplayQueue (waiting for audio fetch)
        while(pendingDisplayQueue.length > 0) {
            const text = pendingDisplayQueue.shift();
            typingQueue.push(...text.split(''));
        }
        
        // 2. If stream finished, ensure we finish typing
        if (isStreamFinished) {
            typingQueue.push(null);
        }
        
        // Trigger fast typing
        if (!isTyping) processTypingQueue();
    }
};

// Queue TTS Function (Pre-fetching)
function queueTTS(text) {
    if (!text.trim()) return;
    
    // Store text in pending queue to preserve order
    pendingDisplayQueue.push(text);
    
    // 1. Start fetching immediately
    // We wrap fetchAudio to attach the original text to the result
    // Catch errors to ensure we always return an object with text
    const audioPromise = fetchAudio(text)
        .then(audio => ({ text, audio }))
        .catch(err => ({ text, audio: null, error: err }));
    
    // 2. Push Promise to Queue
    ttsQueue.push(audioPromise);
    
    // 3. Trigger playback if idle
    if (!isTTSPlaying) {
        processTTSQueue();
    }
}

// Queue End Signal for TTS
function queueTTSEnd() {
    ttsQueue.push(Promise.resolve({ isEnd: true }));
    if (!isTTSPlaying) processTTSQueue();
}

// Process TTS Queue (Sequential Playback & Sync)
async function processTTSQueue() {
    if (ttsQueue.length === 0) {
        isTTSPlaying = false;
        return;
    }
    
    isTTSPlaying = true;
    
    // Get the next audio promise
    const itemPromise = ttsQueue.shift();
    
    try {
        const item = await itemPromise;

        if (item.isEnd) {
            isGenerating = false;
            isTyping = false;
            currentBotMessageDiv = null;
            processTTSQueue();
            return;
        }

        const { text, audio } = item;
        
        // Remove from pendingDisplayQueue as we are about to process it
        const index = pendingDisplayQueue.indexOf(text);
        if (index > -1) pendingDisplayQueue.splice(index, 1);
        
        if (audio) {
            currentAudio = audio;
            
            // Calculate Sync Speed
            // We need duration. If it's a real Audio object, we might need to wait for metadata.
            let duration = 0;
            if (audio instanceof Audio) {
                if (isNaN(audio.duration) || audio.duration === Infinity) {
                     await new Promise(r => {
                        audio.onloadedmetadata = r;
                        // Fallback if event doesn't fire fast enough
                        setTimeout(r, 1000); 
                     });
                }
                duration = audio.duration;
            } else {
                // Fallback dummy object (Web Speech API) - guess duration
                // Avg speaking rate ~ 150 wpm ~ 2.5 words/sec
                const words = text.split(/\s+/).length;
                duration = words / 2.5; 
            }
            
            if (!duration || duration <= 0) duration = text.length * 0.05; // Fallback
            
            // Start Typing Synchronized
            const chars = text.split('');
            const charDelay = (duration * 1000) / chars.length;
            
            // Push to typingQueue but we need a way to control speed per sentence...
            // Standard processTypingQueue uses fixed speed.
            // We will inject a special "sync" mode into processTypingQueue or just use a separate typer.
            
            // SIMPLIFICATION: We will push to typingQueue, but we will throttled it by "playing" status.
            // ACTUALLY: Let's just use a dedicated typer for this sentence.
            
            const typePromise = new Promise(resolve => {
                let charIndex = 0;
                function typeChar() {
                    if (!isTTSPlaying) { resolve(); return; } // Abort if stopped
                    if (charIndex >= chars.length) { resolve(); return; }
                    
                    const char = chars[charIndex++];
                    currentBotMessageContent += char;
                    if (currentBotMessageDiv) {
                        const contentDiv = currentBotMessageDiv.querySelector('.message-content');
                        const answerDiv = contentDiv.querySelector('.final-answer') || contentDiv;
                        answerDiv.innerHTML = marked.parse(currentBotMessageContent);
                        scrollToBottom();
                    }
                    setTimeout(typeChar, charDelay);
                }
                typeChar();
            });

            await new Promise((resolve, reject) => {
                audio.onended = resolve;
                audio.onerror = reject;
                audio.play().catch(reject);
            });
            
            // Ensure typing finishes if audio finished early (or vice versa)
            // But for now let's assume they are roughly synced.
            
        } else {
            // No audio, just show text fast
            typingQueue.push(...text.split(''));
            if (!isTyping) processTypingQueue();
        }
    } catch (e) {
        console.error("Error playing TTS chunk:", e);
    }
    
    // Continue with next chunk IMMEDIATELY
    processTTSQueue();
}

// Fetch Audio (Returns Promise<AudioElement | null>)
async function fetchAudio(text) {
    if (!isTTSEnabled) return null;

    // Simple Markdown strip
    const cleanText = text
        .replace(/\*\*/g, '') 
        .replace(/\*/g, '')
        .replace(/#/g, '')
        .replace(/\[(.*?)\]\(.*?\)/g, '$1')
        .replace(/<[^>]*>/g, '')
        .replace(/http\S+/g, 'đường dẫn'); 

    // 1. Try Local High-Quality TTS (Edge-TTS)
    try {
        const response = await fetch(TTS_URL_BASE + '/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: cleanText })
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            return new Audio(url);
        }
    } catch (e) {
        // Fallback below
    }

    // 2. Fallback: Browser Web Speech API
    // Browser TTS is not async in fetching, but we wrap it to match interface
    // Note: Browser TTS blocks other audio, so we return a dummy "Audio" object that just speaks
    return {
        play: () => {
            return new Promise((resolve, reject) => {
                const utterance = new SpeechSynthesisUtterance(cleanText);
                utterance.lang = 'vi-VN';
                utterance.rate = 1.0;
                
                const voices = window.speechSynthesis.getVoices();
                const vnVoice = voices.find(v => v.lang.includes('vi'));
                if (vnVoice) utterance.voice = vnVoice;

                utterance.onend = () => {
                     // Fire onended to compatibility with real Audio
                    if(this.onended) this.onended(); 
                };
                utterance.onerror = () => {
                    if(this.onerror) this.onerror();
                }; 
                
                window.speechSynthesis.speak(utterance);
            });
        },
        onended: null,
        onerror: null
    };
}

// Handle TTS Streaming
function handleTTSStreaming(textChunk) {
    ttsBuffer += textChunk;
    
    // Split by sentence endings (. ! ? ; \n) followed by space or end
    // Capturing group to keep delimiters
    // Logic: Find the first delimiter. If found, cut sentence, queue it.
    
    const delimiterRegex = /([.?!;:\n]+)/;
    
    let match;
    while ((match = delimiterRegex.exec(ttsBuffer)) !== null) {
        // match[0] is the delimiter
        // match.index is the start of delimiter
        const endIndex = match.index + match[0].length;
        
        const sentence = ttsBuffer.substring(0, endIndex);
        
        // Only queue if it's a reasonable length or a pause
        if (sentence.trim().length > 0) {
            queueTTS(sentence);
        }
        
        ttsBuffer = ttsBuffer.substring(endIndex);
    }
}

function flushTTSBuffer() {
    if (ttsBuffer.trim()) {
        queueTTS(ttsBuffer);
    }
    ttsBuffer = "";
}


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
        // Prevent false timeout message
        if (responseTimer) { clearTimeout(responseTimer); responseTimer = null; }
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
            body: JSON.stringify({ image: currentImageBase64 })
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
    
    // Unlock TTS Audio if enabled (User Interaction Trigger)
    if (isTTSEnabled) {
        // Just create a new Audio to unlock context on interaction
        const dummy = new Audio();
        dummy.play().catch(e => {}); 
    }

    // Clear Input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Prepare Bot Message Placeholder BEFORE sending to handle early progress packets
    isGenerating = true;
    updateSendButtonState();
    isStreamFinished = false; // Reset stream status
    currentBotMessageContent = "";
    typingQueue = [];
    pendingDisplayQueue = [];
    // syncQueue = []; // Was not defined in original file, removing to avoid error if strict mode
    if (typingTimer) clearTimeout(typingTimer);
    isTyping = false;
    
    currentBotMessageDiv = addMessage("", 'bot'); // Empty initially
    
    // Waiting state removed
    
    // Prepare Payload and send
    if (imageToSend) {
        const payload = {
            type: "image_query",
            text: content || "",
            image_base64: imageToSend,
            client_label: currentPredictedLabel
        };
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(payload));
        } else {
            pendingOutbox.push(JSON.stringify(payload));
        }
    } else {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(content);
        } else {
            pendingOutbox.push(content);
        }
    }
    removeImage();

    // Fallback timeout if no response comes back
    if (responseTimer) clearTimeout(responseTimer);
    responseTimer = setTimeout(() => {
        if (isGenerating && currentBotMessageDiv) {
            const contentDiv = currentBotMessageDiv.querySelector('.message-content');
            contentDiv.innerHTML = "<span style='color:#e53e3e'>Máy chủ phản hồi chậm hoặc mất kết nối. Vui lòng thử lại.</span>";
            isGenerating = false;
            updateSendButtonState();
        }
    }, 20000);
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
        if (responseTimer) { clearTimeout(responseTimer); responseTimer = null; }
        // Ensure typing area exists; keep any progress list
        const typingIcon = contentDiv.querySelector('.typing-indicator');
        if (typingIcon) typingIcon.remove();
        let answerDiv = contentDiv.querySelector('.final-answer');
        if (!answerDiv) {
            answerDiv = document.createElement('div');
            answerDiv.className = 'final-answer';
            contentDiv.appendChild(answerDiv);
        }
        
        // TTS Streaming Hook
        if (isTTSEnabled) {
             handleTTSStreaming(data.content);
        } else {
            // Push characters to queue ONLY if TTS is OFF
            const chars = data.content.split('');
            typingQueue.push(...chars);
            // Start typing if not already
            if (!isTyping) {
                processTypingQueue();
            }
        }
    } 
    else if (data.type === 'start') {
        if (responseTimer) { clearTimeout(responseTimer); responseTimer = null; }
    }
    else if (data.type === 'end') {
        if (responseTimer) { clearTimeout(responseTimer); responseTimer = null; }
        isStreamFinished = true;
        // Allow user to send tiếp ngay sau khi luồng kết thúc,
        // kể cả khi TTS còn đang phát lại
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
        // TTS Flush Hook
        if (isTTSEnabled) {
            flushTTSBuffer();
            queueTTSEnd();
        } else {
             // Push end signal
            typingQueue.push(null);
            if (!isTyping) processTypingQueue();
        }
    }
    else if (data.type === 'error') {
        if (responseTimer) { clearTimeout(responseTimer); responseTimer = null; }
        contentDiv.innerHTML += `<br><span style="color: red;">Error: ${data.content}</span>`;
        isGenerating = false;
        updateSendButtonState();
        typingQueue = [];
    }
    else if (data.type === 'progress') {
        if (responseTimer) { clearTimeout(responseTimer); responseTimer = null; }
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
