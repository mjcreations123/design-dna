const menu = document.querySelector('.menu-panel');
document.querySelector('.menu-toggle').addEventListener('click', () => {
  menu.classList.add('is-open');
  menu.setAttribute('aria-hidden', 'false');
});
document.querySelector('.menu-close').addEventListener('click', () => {
  menu.classList.remove('is-open');
  menu.setAttribute('aria-hidden', 'true');
});

for (const button of document.querySelectorAll('.role-card')) {
  button.addEventListener('click', () => {
    const detail = document.getElementById(button.dataset.detail);
    detail.hidden = !detail.hidden;
  });
}

document.querySelector('.dead-primary').addEventListener('click', (event) => {
  event.currentTarget.style.filter = 'saturate(1.08)';
});
