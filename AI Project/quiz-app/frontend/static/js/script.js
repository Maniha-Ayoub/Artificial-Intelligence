// --- Auth Logic ---
// Safety reset: Clear any leftover anti-cheat locks from previous sessions
window.onbeforeunload = null;

function toggleForm(target = 'register') {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const adminForm = document.getElementById('admin-login-form');
    
    if(loginForm) loginForm.classList.add('hidden');
    if(registerForm) registerForm.classList.add('hidden');
    if(adminForm) adminForm.classList.add('hidden');

    if (target === 'login' && loginForm) {
        loginForm.classList.remove('hidden');
    } else if (target === 'register' && registerForm) {
        registerForm.classList.remove('hidden');
    } else if (target === 'admin' && adminForm) {
        adminForm.classList.remove('hidden');
    }
    
    document.getElementById('auth-error').classList.add('hidden');
}

async function handleAuth(type) {
    const errorEl = document.getElementById('auth-error');
    errorEl.classList.add('hidden');
    
    let payload = {};
    let endpoint = type;
    if (type === 'login') {
        payload.email = document.getElementById('login-email').value;
        payload.password = document.getElementById('login-password').value;
    } else if (type === 'admin_login') {
        payload.email = document.getElementById('admin-email').value;
        payload.password = document.getElementById('admin-password').value;
        endpoint = 'login';
    } else {
        payload.name = document.getElementById('reg-name').value;
        payload.email = document.getElementById('reg-email').value;
        payload.password = document.getElementById('reg-password').value;
    }

    try {
        const res = await fetch(`/api/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            if (data.role === 'admin') {
                window.location.href = '/admin_dashboard';
            } else {
                window.location.href = '/dashboard';
            }
        } else {
            errorEl.innerText = data.error || "Authentication failed.";
            errorEl.classList.remove('hidden');
        }
    } catch (e) {
        errorEl.innerText = "Network error. Please try again.";
        errorEl.classList.remove('hidden');
    }
}

async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/';
}

function startQuiz(category) {
    localStorage.setItem('selectedCategory', category);
    window.location.href = '/quiz';
}


// --- Cheat Detection Logic ---
let cheatWarnings = 0;
const MAX_WARNINGS = 3;

function triggerCheatWarning(reason) {
    if (document.getElementById('result-screen') && !document.getElementById('result-screen').classList.contains('hidden')) return;
    if (document.getElementById('loading-screen') && !document.getElementById('loading-screen').classList.contains('hidden') && currentQuestionIndex === 0) return;

    cheatWarnings++;
    
    const cheatUI = document.getElementById('cheat-warning');
    const cheatText = document.getElementById('cheat-text');
    if (cheatUI) {
        cheatUI.classList.remove('hidden');
        cheatText.innerText = `${reason} (Warning ${cheatWarnings}/${MAX_WARNINGS})`;
        
        setTimeout(() => { cheatUI.classList.add('hidden'); }, 4000);
    }

    if (cheatWarnings >= MAX_WARNINGS) {
        alert("Maximum warnings reached. Quiz terminated.");
        finishQuiz();
    }
}

// --- Cheat Detection Removed from Learning Mode (Now in Exam Mode) ---

// --- Voice Logic ---
function readQuestionOutLoud() {
    if (!currentQuestionData) return;
    window.speechSynthesis.cancel();
    const textToSpeak = `${currentQuestionData.question}. Option A: ${currentQuestionData.option_a}. Option B: ${currentQuestionData.option_b}. Option C: ${currentQuestionData.option_c}. Option D: ${currentQuestionData.option_d}.`;
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
}

function startVoiceRecognition() {
    const voiceBtn = document.getElementById('voice-btn');
    if (!('webkitSpeechRecognition' in window)) {
        alert("Voice recognition is not supported in this browser.");
        return;
    }
    const recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = function() {
        voiceBtn.innerText = "Listening...";
        voiceBtn.style.background = "rgba(239, 68, 68, 0.2)";
    };

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript.trim().toLowerCase();
        let selectedKey = null;
        if (transcript.match(/\b(a|hey|option a)\b/)) selectedKey = 'A';
        else if (transcript.match(/\b(b|be|option b)\b/)) selectedKey = 'B';
        else if (transcript.match(/\b(c|see|sea|option c)\b/)) selectedKey = 'C';
        else if (transcript.match(/\b(d|the|option d)\b/)) selectedKey = 'D';

        if (selectedKey) {
            const btns = UI.optionsContainer.querySelectorAll('.option-btn');
            for (let btn of btns) {
                if (btn.querySelector('.option-letter').innerText === selectedKey) {
                    handleOptionClick(selectedKey, btn);
                    break;
                }
            }
        } else {
            alert(`Heard: "${transcript}". Please say "A", "B", "C", or "D".`);
        }
    };

    recognition.onerror = function(event) {
        voiceBtn.innerText = "🎤 Speak Answer";
        voiceBtn.style.background = "transparent";
    };

    recognition.onend = function() {
        voiceBtn.innerText = "🎤 Speak Answer";
        voiceBtn.style.background = "transparent";
    };

    recognition.start();
}

// --- Quiz Logic ---
const totalQuestions = 5;
let currentQuestionIndex = 0;
let score = 0;
let currentDifficulty = 'Easy';
let selectedCategory = localStorage.getItem('selectedCategory') || 'Python';
let currentQuestionData = null;
let quizHistory = [];
let timerInterval;
let secondsElapsed = 0;

const UI = {
    loadingScreen: document.getElementById('loading-screen'),
    questionScreen: document.getElementById('question-screen'),
    resultScreen: document.getElementById('result-screen'),
    qNum: document.getElementById('q-num'),
    totalQ: document.getElementById('total-q'),
    categoryLabel: document.getElementById('category-label'),
    questionText: document.getElementById('question-text'),
    optionsContainer: document.getElementById('options-container'),
    progressFill: document.getElementById('progress-fill'),
    timer: document.getElementById('timer'),
    diffBadge: document.getElementById('current-difficulty')
};

document.addEventListener('DOMContentLoaded', () => {
    if(window.location.pathname === '/quiz') {
        initQuiz();
    } else if(window.location.pathname === '/dashboard') {
        fetchUserStats();
    }
});

async function initQuiz() {
    UI.totalQ.innerText = totalQuestions;
    UI.categoryLabel.innerText = selectedCategory;
    startTimer();
    preventBackNavigation();
    await fetchNextQuestion();
}

function preventBackNavigation() {
    // Push a new state to the history stack
    history.pushState(null, null, location.href);
    // When the user clicks back, force them forward again
    window.onpopstate = function () {
        history.go(1);
    };
    // Warn before reloading or closing the tab
    window.onbeforeunload = function() {
        return "Are you sure you want to leave? Your quiz progress will be lost.";
    };
}

function allowBackNavigation() {
    window.onpopstate = null;
    window.onbeforeunload = null;
}

function updateTimerDisplay() {
    const m = String(Math.floor(secondsElapsed / 60)).padStart(2, '0');
    const s = String(secondsElapsed % 60).padStart(2, '0');
    UI.timer.innerText = `${m}:${s}`;
}

function startTimer() {
    timerInterval = setInterval(() => {
        secondsElapsed++;
        updateTimerDisplay();
    }, 1000);
}

function updateDifficultyBadge(diff) {
    UI.diffBadge.innerText = diff;
    UI.diffBadge.className = `value badge-${diff.toLowerCase()}`;
}

async function fetchNextQuestion() {
    UI.questionScreen.classList.add('hidden');
    UI.loadingScreen.classList.remove('hidden');

    try {
        const response = await fetch(`/api/questions?category=${selectedCategory}&difficulty=${currentDifficulty}`);
        
        if (response.status === 401) {
            window.location.href = '/'; // Unauthorized
            return;
        }
        
        if (!response.ok) throw new Error("Failed to fetch question");
        const data = await response.json();
        
        currentQuestionData = data;
        renderQuestion(data);
    } catch (error) {
        console.error("Error fetching question:", error);
        UI.questionText.innerText = "Network or AI Error: Unable to fetch the next question. You can end the quiz now to save your current score.";
        UI.optionsContainer.innerHTML = `<button class="btn primary-btn" onclick="finishQuiz()">End Quiz & Save Score</button>`;
        UI.loadingScreen.classList.add('hidden');
        UI.questionScreen.classList.remove('hidden');
    }
}

function renderQuestion(data) {
    currentQuestionIndex++;
    UI.qNum.innerText = currentQuestionIndex;
    updateDifficultyBadge(currentDifficulty);
    
    UI.progressFill.style.width = `${((currentQuestionIndex - 1) / totalQuestions) * 100}%`;

    UI.questionText.innerText = data.question;
    UI.optionsContainer.innerHTML = '';

    const options = [
        { key: 'A', text: data.option_a },
        { key: 'B', text: data.option_b },
        { key: 'C', text: data.option_c },
        { key: 'D', text: data.option_d }
    ];

    options.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.innerHTML = `<span class="option-letter">${opt.key}</span> ${opt.text}`;
        btn.onclick = () => handleOptionClick(opt.key, btn);
        UI.optionsContainer.appendChild(btn);
    });

    UI.loadingScreen.classList.add('hidden');
    UI.questionScreen.classList.remove('hidden');
}

async function handleOptionClick(selectedKey, btnElement) {
    window.speechSynthesis.cancel();
    
    const allBtns = UI.optionsContainer.querySelectorAll('.option-btn');
    allBtns.forEach(b => b.onclick = null);

    const isCorrect = selectedKey === currentQuestionData.correct_answer;
    
    if (isCorrect) {
        btnElement.classList.add('correct');
        score++;
    } else {
        btnElement.classList.add('incorrect');
        allBtns.forEach(b => {
            if(b.innerText.startsWith(currentQuestionData.correct_answer)) {
                b.classList.add('correct');
            }
        });
    }

    quizHistory.push({
        question: currentQuestionData.question,
        isCorrect: isCorrect,
        difficulty: currentDifficulty
    });

    // Show AI Explanation
    await showAIExplanation(selectedKey, isCorrect);
    
    // Show Next Button
    document.getElementById('next-btn').classList.remove('hidden');
    document.getElementById('hint-btn').classList.add('hidden');
}

async function showAIExplanation(selectedKey, isCorrect) {
    const explanationSection = document.getElementById('explanation-section');
    const explanationText = document.getElementById('explanation-text');
    
    explanationSection.classList.remove('hidden');
    explanationText.innerText = "AI is thinking...";
    
    const optionsMap = {
        'A': currentQuestionData.option_a,
        'B': currentQuestionData.option_b,
        'C': currentQuestionData.option_c,
        'D': currentQuestionData.option_d
    };

    try {
        const res = await fetch('/api/explanation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                question: currentQuestionData.question,
                correct_answer: currentQuestionData.correct_answer,
                selected_answer: selectedKey,
                options_map: optionsMap
            })
        });
        const data = await res.json();
        explanationText.innerText = data.explanation;
    } catch (e) {
        explanationText.innerText = isCorrect ? "Correct! Well done." : `The correct answer was ${currentQuestionData.correct_answer}.`;
    }
}

async function handleNextQuestion() {
    document.getElementById('explanation-section').classList.add('hidden');
    document.getElementById('hint-section').classList.add('hidden');
    document.getElementById('next-btn').classList.add('hidden');
    document.getElementById('hint-btn').classList.remove('hidden');
    
    const lastResult = quizHistory[quizHistory.length - 1];
    
    if (currentQuestionIndex < totalQuestions) {
        await determineNextDifficulty(lastResult.isCorrect);
        await fetchNextQuestion();
    } else {
        finishQuiz();
    }
}

async function getAIHint() {
    if (!currentQuestionData) return;
    
    const hintBtn = document.getElementById('hint-btn');
    const hintLoading = document.getElementById('hint-loading');
    const hintSection = document.getElementById('hint-section');
    const hintText = document.getElementById('hint-text');
    
    hintBtn.disabled = true;
    hintLoading.classList.remove('hidden');
    
    const options = `A) ${currentQuestionData.option_a}, B) ${currentQuestionData.option_b}, C) ${currentQuestionData.option_c}, D) ${currentQuestionData.option_d}`;

    try {
        const res = await fetch('/api/hint', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                question: currentQuestionData.question,
                options: options
            })
        });
        const data = await res.json();
        hintText.innerText = data.hint;
        hintSection.classList.remove('hidden');
    } catch (e) {
        alert("Hint unavailable.");
    } finally {
        hintBtn.disabled = false;
        hintLoading.classList.add('hidden');
    }
}

async function determineNextDifficulty(isCorrect) {
    try {
        const res = await fetch('/api/next_difficulty', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ current_difficulty: currentDifficulty, is_correct: isCorrect })
        });
        const data = await res.json();
        currentDifficulty = data.next_difficulty;
    } catch (e) {
        const levels = ['Easy', 'Medium', 'Hard'];
        let idx = levels.indexOf(currentDifficulty);
        if(isCorrect) idx = Math.min(idx+1, 2);
        else idx = Math.max(idx-1, 0);
        currentDifficulty = levels[idx];
    }
}

async function finishQuiz() {
    clearInterval(timerInterval);
    allowBackNavigation();
    UI.progressFill.style.width = '100%';
    
    UI.questionScreen.classList.add('hidden');
    UI.resultScreen.classList.remove('hidden');

    document.getElementById('final-score').innerText = score;
    document.getElementById('final-total').innerText = totalQuestions;
    
    const pct = (score / totalQuestions) * 100;
    document.querySelector('.score-circle').style.setProperty('--score-pct', pct);

    try {
        const detailsStr = quizHistory.map((q, i) => `Q${i+1} (${q.difficulty}): ${q.isCorrect ? 'Correct' : 'Incorrect'}`).join(', ');
        
        const res = await fetch('/api/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                score: score,
                total: totalQuestions,
                category: selectedCategory,
                details: detailsStr
            })
        });
        
        const data = await res.json();
        
        document.getElementById('ai-loading').classList.add('hidden');
        const feedbackEl = document.getElementById('ai-feedback-text');
        feedbackEl.innerText = data.ai_feedback || "Great job completing the quiz!";
        feedbackEl.classList.remove('hidden');
        
        // Handle new badges
        if (data.new_badges && data.new_badges.length > 0) {
            data.new_badges.forEach(badgeName => {
                showBadgeNotification(badgeName);
            });
        }
        
    } catch (e) {
        document.getElementById('ai-loading').classList.add('hidden');
        document.getElementById('ai-feedback-text').innerText = "Feedback unavailable at the moment.";
        document.getElementById('ai-feedback-text').classList.remove('hidden');
    }
}

function showBadgeNotification(badgeName) {
    const notification = document.createElement('div');
    notification.className = 'badge-notification';
    notification.innerHTML = `
        <div class="badge-notif-content">
            <div class="badge-notif-icon">🏆</div>
            <div class="badge-notif-text">
                <div class="badge-notif-title">New Badge Earned!</div>
                <div class="badge-notif-name">${badgeName}</div>
            </div>
        </div>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 500);
    }, 4000);
}

// --- Custom Quiz feature removed ---

async function generateQuizFromPDF() {
    const fileInput = document.getElementById('pdf-file');
    const file = fileInput.files[0];
    
    if (!file) {
        alert("Please select a PDF file first.");
        return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
        alert("Please upload a valid PDF file.");
        return;
    }

    const btn = document.getElementById('pdf-generate-btn');
    const loading = document.getElementById('pdf-generation-loading');
    const errorEl = document.getElementById('pdf-generation-error');

    btn.disabled = true;
    loading.classList.remove('hidden');
    loading.style.display = 'flex';
    errorEl.classList.add('hidden');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/generate_quiz_from_pdf', {
            method: 'POST',
            body: formData // Fetch automatically sets Content-Type to multipart/form-data with boundary
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Reload page to show new category card
            window.location.reload();
        } else {
            errorEl.innerText = data.error || "Failed to process PDF. Please try again.";
            errorEl.classList.remove('hidden');
            btn.disabled = false;
            loading.classList.add('hidden');
        }
    } catch (error) {
        console.error("PDF Upload Error:", error);
        errorEl.innerText = "Network error or file too large. Please try again.";
        errorEl.classList.remove('hidden');
        btn.disabled = false;
        loading.classList.add('hidden');
    }
}
async function fetchUserStats() {
    try {
        const res = await fetch('/api/user_stats');
        const data = await res.json();
        if (data.stats) {
            document.getElementById('user-streak').innerText = `${data.stats.current_streak || 0} Days`;
            document.getElementById('user-points').innerText = data.stats.points || 0;
        }
        
        const badgesList = document.getElementById('badges-list');
        if (badgesList && data.badges) {
            badgesList.innerHTML = '';
            data.badges.forEach(badge => {
                const badgeEl = document.createElement('div');
                badgeEl.className = 'badge-item';
                badgeEl.title = badge.description;
                badgeEl.innerHTML = `
                    <div class="badge-icon" style="background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 20px; font-size: 0.7rem; border: 1px solid var(--border-subtle);">
                        <i class="fas ${badge.icon_path}"></i> ${badge.name}
                    </div>
                `;
                badgesList.appendChild(badgeEl);
            });
        }
    } catch (e) {
        console.error("Error fetching stats:", e);
    }
}

async function showLeaderboard() {
    const modal = document.getElementById('leaderboard-modal');
    const list = document.getElementById('leaderboard-list');
    
    modal.classList.remove('hidden');
    list.innerHTML = '<p style="text-align: center; color: var(--text-muted);">Loading scores...</p>';
    
    try {
        const res = await fetch('/api/leaderboard');
        const data = await res.json();
        
        list.innerHTML = '';
        data.forEach((user, index) => {
            const entry = document.createElement('div');
            entry.className = 'leaderboard-entry';
            entry.style = 'display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; background: rgba(255,255,255,0.05); border-radius: 6px; margin-bottom: 0.5rem;';
            entry.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="color: ${index < 3 ? 'var(--primary)' : 'var(--text-muted)'}; font-weight: 800;">#${index + 1}</span>
                    <span style="color: white; font-weight: 600;">${user.name}</span>
                </div>
                <div style="text-align: right;">
                    <div style="color: var(--secondary); font-weight: 700;">${user.points} pts</div>
                    <div style="font-size: 0.65rem; color: #ff9800;">${user.current_streak}d streak</div>
                </div>
            `;
            list.appendChild(entry);
        });
    } catch (e) {
        list.innerHTML = '<p style="color: var(--diff-hard);">Failed to load leaderboard.</p>';
    }
}

function closeLeaderboard() {
    document.getElementById('leaderboard-modal').classList.add('hidden');
}
// --- End of script ---
// Final safety check to ensure UI is unlocked on script load
window.onbeforeunload = null;
