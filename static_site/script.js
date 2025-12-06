// Smooth scroll for internal anchors
document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    const target = document.querySelector(link.getAttribute('href'));
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// CTA shortcuts
const ctaPrimary = document.getElementById('cta-primary');
const ctaSecondary = document.getElementById('cta-secondary');
if (ctaPrimary) {
  ctaPrimary.addEventListener('click', () => {
    document.querySelector('#apps')?.scrollIntoView({ behavior: 'smooth' });
  });
}
if (ctaSecondary) {
  ctaSecondary.addEventListener('click', () => {
    document.querySelector('#contact')?.scrollIntoView({ behavior: 'smooth' });
  });
}

// App card actions (placeholder hooks)
document.querySelectorAll('[data-launch]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const target = btn.getAttribute('data-launch');
    // Wire these to real app URLs or modals as needed.
    if (target === 'territory') {
      window.location.href = '/app'; // streamlit proxied under /app
    } else {
      alert('Coming soon. Reach out to add the next app.');
    }
  });
});
