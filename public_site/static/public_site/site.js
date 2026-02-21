(function () {
  const navBtn = document.querySelector('[data-nav-toggle]');
  const navMenu = document.querySelector('[data-nav-menu]');
  if (navBtn && navMenu) {
    navBtn.addEventListener('click', function () {
      navMenu.classList.toggle('open');
    });
  }

  const carousel = document.querySelector('[data-carousel]');
  if (!carousel) return;

  const slides = Array.from(carousel.querySelectorAll('.hero-slide'));
  const next = carousel.querySelector('[data-carousel-next]');
  const prev = carousel.querySelector('[data-carousel-prev]');
  const dotsWrap = carousel.querySelector('[data-carousel-dots]');
  if (!slides.length) return;

  let idx = 0;
  let timer = null;

  function renderDots() {
    if (!dotsWrap) return;
    dotsWrap.innerHTML = '';
    slides.forEach(function (_, i) {
      const dot = document.createElement('button');
      dot.type = 'button';
      if (i === idx) dot.classList.add('active');
      dot.setAttribute('aria-label', 'Go to slide ' + (i + 1));
      dot.addEventListener('click', function () {
        idx = i;
        paint();
        restart();
      });
      dotsWrap.appendChild(dot);
    });
  }

  function paint() {
    slides.forEach(function (el, i) {
      el.classList.toggle('active', i === idx);
    });
    renderDots();
  }

  function step(dir) {
    idx = (idx + dir + slides.length) % slides.length;
    paint();
  }

  function restart() {
    if (timer) clearInterval(timer);
    timer = setInterval(function () { step(1); }, 5200);
  }

  if (next) next.addEventListener('click', function () { step(1); restart(); });
  if (prev) prev.addEventListener('click', function () { step(-1); restart(); });

  paint();
  restart();
})();
