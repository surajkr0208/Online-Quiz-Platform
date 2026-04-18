// ─── Theme Management ──────────────────────────────────────────
const THEME_KEY = 'quizplatform_theme';

function getTheme() {
  return localStorage.getItem(THEME_KEY) || 'light';
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
  const toggle = document.getElementById('themeToggle');
  if (toggle) toggle.checked = (theme === 'dark');
}

function toggleTheme() {
  const current = getTheme();
  setTheme(current === 'dark' ? 'light' : 'dark');
}

// Apply theme immediately to prevent flash
(function() {
  const t = localStorage.getItem(THEME_KEY) || 'light';
  document.documentElement.setAttribute('data-theme', t);
})();

document.addEventListener('DOMContentLoaded', function () {
  // ─── Set Toggle State ─────────────────────────────────────────
  const toggle = document.getElementById('themeToggle');
  if (toggle) {
    toggle.checked = getTheme() === 'dark';
    toggle.addEventListener('change', toggleTheme);
  }

  // ─── Scroll Animations ────────────────────────────────────────
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          entry.target.classList.add('visible');
        }, i * 80);
      }
    });
  }, { threshold: 0.08 });

  document.querySelectorAll('.animate-on-scroll').forEach(el => {
    observer.observe(el);
  });
});

// ─── Quiz Timer ────────────────────────────────────────────────
class QuizTimer {
  constructor(seconds, onTick, onExpire) {
    this.totalSeconds = seconds;
    this.remaining = seconds;
    this.onTick = onTick;
    this.onExpire = onExpire;
    this.interval = null;
  }

  start() {
    this.interval = setInterval(() => {
      this.remaining--;
      this.onTick(this.remaining, this.totalSeconds);
      if (this.remaining <= 0) {
        this.stop();
        this.onExpire();
      }
    }, 1000);
  }

  stop() {
    clearInterval(this.interval);
    this.interval = null;
  }

  reset(seconds) {
    this.stop();
    this.totalSeconds = seconds;
    this.remaining = seconds;
  }
}

// ─── Score Circle Animation ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const circle = document.querySelector('.score-circle');
  if (circle) {
    const pct = parseFloat(circle.style.getPropertyValue('--pct') || circle.getAttribute('data-pct') || 0);
    let current = 0;
    const duration = 1200;
    const steps = 60;
    const increment = pct / steps;
    const timer = setInterval(() => {
      current += increment;
      if (current >= pct) {
        current = pct;
        clearInterval(timer);
      }
      circle.style.setProperty('--pct', current);
    }, duration / steps);
  }
});
