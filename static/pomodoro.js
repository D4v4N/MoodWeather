console.log("pomodoro.js loaded");

let defaultMinutes = 25;
let timeLeft = defaultMinutes * 60;
let timerInterval = null;

function updateTimer() {
    const timerEl = document.getElementById("timer");
    if (!timerEl) return;

    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;

    timerEl.textContent =
        `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function startTimer() {
    if (timerInterval) return;

    timerInterval = setInterval(() => {
        if (timeLeft > 0) {
            timeLeft--;
            updateTimer();
        } else {
            clearInterval(timerInterval);
            timerInterval = null;

            const audio = new Audio("https://actions.google.com/sounds/v1/alarms/alarm_clock.ogg");
            audio.play();
        }
    }, 1000);
}

function pauseTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
}

function resetTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
    timeLeft = defaultMinutes * 60;
    updateTimer();
}

function setTimerMinutes(minutes) {
    clearInterval(timerInterval);
    timerInterval = null;
    defaultMinutes = minutes;
    timeLeft = minutes * 60;
    updateTimer();
}

window.startTimer = startTimer;
window.pauseTimer = pauseTimer;
window.resetTimer = resetTimer;
window.setTimerMinutes = setTimerMinutes;

updateTimer();