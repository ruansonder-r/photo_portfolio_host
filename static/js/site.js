// Note: Tailwind config is set in templates before the CDN script is loaded.

// Utility: clipboard copy via data-copy-target
function handleClipboardClick(event) {
  const targetSelector = event.currentTarget.getAttribute('data-copy-target');
  if (!targetSelector) return;
  const element = document.querySelector(targetSelector);
  if (!element) return;
  if (element.select) {
    element.select();
    element.setSelectionRange(0, 99999);
  }
  let copied = false;
  try {
    if (navigator.clipboard && element.value !== undefined) {
      navigator.clipboard.writeText(element.value);
      copied = true;
    } else {
      copied = document.execCommand('copy');
    }
  } catch (_) {}
  if (copied) {
    const button = event.currentTarget;
    const originalText = button.textContent;
    button.textContent = '✅ Copied!';
    button.classList.add('bg-green-600');
    setTimeout(() => {
      button.textContent = originalText;
      button.classList.remove('bg-green-600');
    }, 2000);
  }
}

// Carousel (page-level, first .carousel in DOM)
function initCarousel() {
  const carousel = document.querySelector('.carousel-container .carousel');
  if (!carousel) return;
  const slides = carousel.querySelectorAll('.carousel-slide');
  const prevBtn = document.querySelector('.carousel-container .carousel-prev');
  const nextBtn = document.querySelector('.carousel-container .carousel-next');
  let currentSlide = 0;
  const totalSlides = slides.length;
  let autoAdvanceInterval;
  let touchStartX = 0, touchStartY = 0;
  let touchEndX = 0, touchEndY = 0;
  let isDragging = false;

  function updateCarousel() {
    carousel.style.transform = `translateX(-${currentSlide * 100}%)`;
  }
  function nextSlide() { currentSlide = (currentSlide + 1) % totalSlides; updateCarousel(); }
  function prevSlide() { currentSlide = (currentSlide - 1 + totalSlides) % totalSlides; updateCarousel(); }
  function startAutoAdvance() { if (totalSlides > 1) autoAdvanceInterval = setInterval(nextSlide, 6000); }
  function stopAutoAdvance() { if (autoAdvanceInterval) clearInterval(autoAdvanceInterval); }

  function handleTouchStart(e) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    isDragging = true;
    stopAutoAdvance();
  }
  function handleTouchMove(e) {
    if (!isDragging) return;
    e.preventDefault();
    touchEndX = e.touches[0].clientX;
    touchEndY = e.touches[0].clientY;
    const diffX = touchStartX - touchEndX;
    const translateX = -currentSlide * 100 - (diffX / carousel.offsetWidth) * 100;
    carousel.style.transform = `translateX(${translateX}%)`;
  }
  function handleTouchEnd() {
    if (!isDragging) return;
    isDragging = false;
    const diffX = touchStartX - touchEndX;
    const diffY = touchStartY - touchEndY;
    const threshold = 50;
    if (diffY > threshold && Math.abs(diffY) > Math.abs(diffX)) {
      const modal = carousel.closest('.modal-carousel');
      if (modal) closeModalCarousel();
      return;
    }
    if (Math.abs(diffX) > threshold) {
      diffX > 0 ? nextSlide() : prevSlide();
    } else {
      updateCarousel();
    }
    startAutoAdvance();
  }

  carousel.addEventListener('touchstart', handleTouchStart, { passive: false });
  carousel.addEventListener('touchmove', handleTouchMove, { passive: false });
  carousel.addEventListener('touchend', handleTouchEnd, { passive: false });
  if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); stopAutoAdvance(); startAutoAdvance(); });
  if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); stopAutoAdvance(); startAutoAdvance(); });
  carousel.addEventListener('mouseenter', stopAutoAdvance);
  carousel.addEventListener('mouseleave', startAutoAdvance);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') { prevSlide(); stopAutoAdvance(); startAutoAdvance(); }
    else if (e.key === 'ArrowRight') { nextSlide(); stopAutoAdvance(); startAutoAdvance(); }
    else if (e.key === 'Escape') {
      const isInModal = !!carousel.closest('.modal-carousel');
      if (isInModal) closeModalCarousel();
    }
  });
  updateCarousel();
  startAutoAdvance();
}

// Modal Carousel logic (global)
function openModalCarousel(images, startIndex = 0) {
  const modal = document.getElementById('modalCarousel');
  const modalCarouselInner = document.getElementById('modalCarouselInner');
  if (!modal || !modalCarouselInner) return;
  modalCarouselInner.innerHTML = '';
  images.forEach((image) => {
    const slide = document.createElement('div');
    slide.className = 'carousel-slide';
    slide.innerHTML = `
      <div class="carousel-card">
        <img src="${image.download_url}" alt="${image.name}" loading="lazy">
      </div>
    `;
    modalCarouselInner.appendChild(slide);
  });
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';
  window.modalCarousel = modalCarouselInner;
  window.modalCurrentSlide = startIndex;
  updateModalCarousel();
  initModalTouchEvents();
  const prevBtn = document.getElementById('modalCarouselPrev');
  const nextBtn = document.getElementById('modalCarouselNext');
  if (prevBtn) prevBtn.onclick = prevModalSlide;
  if (nextBtn) nextBtn.onclick = nextModalSlide;
}

function closeModalCarousel() {
  const modal = document.getElementById('modalCarousel');
  if (!modal) return;
  modal.classList.remove('active');
  document.body.style.overflow = '';
  window.modalCarousel = null;
}

function updateModalCarousel() {
  if (window.modalCarousel) {
    window.modalCarousel.style.transform = `translateX(-${window.modalCurrentSlide * 100}%)`;
  }
}

function nextModalSlide() {
  if (window.modalCarousel) {
    const slides = window.modalCarousel.querySelectorAll('.carousel-slide');
    window.modalCurrentSlide = (window.modalCurrentSlide + 1) % slides.length;
    updateModalCarousel();
  }
}

function prevModalSlide() {
  if (window.modalCarousel) {
    const slides = window.modalCarousel.querySelectorAll('.carousel-slide');
    window.modalCurrentSlide = (window.modalCurrentSlide - 1 + slides.length) % slides.length;
    updateModalCarousel();
  }
}

function initModalTouchEvents() {
  if (!window.modalCarousel) return;
  let touchStartX = 0, touchStartY = 0;
  let touchEndX = 0, touchEndY = 0;
  let isDragging = false;
  function handleStart(e) { touchStartX = e.touches[0].clientX; touchStartY = e.touches[0].clientY; isDragging = true; }
  function handleMove(e) {
    if (!isDragging) return;
    e.preventDefault();
    touchEndX = e.touches[0].clientX; touchEndY = e.touches[0].clientY;
    const diffX = touchStartX - touchEndX;
    const translateX = -window.modalCurrentSlide * 100 - (diffX / window.modalCarousel.offsetWidth) * 100;
    window.modalCarousel.style.transform = `translateX(${translateX}%)`;
  }
  function handleEnd() {
    if (!isDragging) return;
    isDragging = false;
    const diffX = touchStartX - touchEndX;
    const diffY = touchStartY - touchEndY;
    const threshold = 50;
    if (diffY > threshold && Math.abs(diffY) > Math.abs(diffX)) { closeModalCarousel(); return; }
    if (Math.abs(diffX) > threshold) { diffX > 0 ? nextModalSlide() : prevModalSlide(); } else { updateModalCarousel(); }
  }
  window.modalCarousel.addEventListener('touchstart', handleStart, { passive: false });
  window.modalCarousel.addEventListener('touchmove', handleMove, { passive: false });
  window.modalCarousel.addEventListener('touchend', handleEnd, { passive: false });
}

// Expose globally for templates that call these
window.openModalCarousel = openModalCarousel;
window.closeModalCarousel = closeModalCarousel;

// DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  // Clipboard buttons
  document.querySelectorAll('[data-copy-target]').forEach((btn) => {
    btn.addEventListener('click', handleClipboardClick);
  });
  // Close modal
  const closeBtn = document.getElementById('modalCloseBtn');
  if (closeBtn) closeBtn.addEventListener('click', closeModalCarousel);
  // Init page carousel
  initCarousel();
});


