(() => {
  'use strict';
  const stage = document.querySelector('#stage');
  const scene = document.querySelector('#scene');
  const scrub = document.querySelector('#scrub');
  const message = document.querySelector('#message');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const cards = new Map();
  const viewer = document.querySelector('#viewer');
  const viewerImage = document.querySelector('#viewer-image');
  let velocity = 0, inputVelocity = 0, lastWheel = 0, landing = null;
  const viewerBackground = document.querySelector('#viewer-background');
  let viewerAnimation = null, sourceAnimation = null, backdropAnimation = null, returnFocus = null, viewingIndex = null, closingViewer = false;
  let motionMode = 'wheel', springFrequency = 7, travel = null;
  function sizeViewer() {
    if (!viewerImage.naturalWidth) return;
    const ratio = viewerImage.naturalWidth / viewerImage.naturalHeight;
    const height = Math.min(innerHeight, innerWidth * .94 / ratio);
    viewerImage.style.height = `${height}px`;
    viewerImage.style.width = `${height * ratio}px`;
  }
  viewerImage.addEventListener('load', sizeViewer);
  function fitImage(image, card) {
    if (!image.naturalWidth) return;
    const scale = Math.min(card.clientWidth / image.naturalWidth, card.clientHeight / image.naturalHeight);
    image.style.width = `${image.naturalWidth * scale}px`;
    image.style.height = `${image.naturalHeight * scale}px`;
  }
  // Measure the rendered corners instead of reconstructing nested CSS perspective.
  // Opacity flattens CSS 3-D layers, so multiplying their transforms is not equivalent.
  function stackTransform() {
    const card = cards.get(viewingIndex);
    const source = card.querySelector('img');
    const plane = source.parentElement;
    const style = getComputedStyle(source);
    const width = parseFloat(style.width), height = parseFloat(style.height);
    const corners = [[0, 0], [1, 0], [1, 1], [0, 1]];
    const markers = corners.map(([u, v]) => {
      const marker = document.createElement('span');
      marker.style.cssText = `position:absolute;pointer-events:none;width:0;height:0;left:calc(50% + ${(u - .5) * width}px);top:calc(50% + ${(v - .5) * height}px)`;
      plane.append(marker);
      return marker;
    });
    const points = markers.map(marker => {
      const rect = marker.getBoundingClientRect();
      return [rect.x, rect.y];
    });
    markers.forEach(marker => marker.remove());
    // Solve the projective mapping from a unit rectangle to the measured quadrilateral.
    const rows = corners.flatMap(([u, v], i) => {
      const [x, y] = points[i];
      return [[u, v, 1, 0, 0, 0, -x * u, -x * v, x],
              [0, 0, 0, u, v, 1, -y * u, -y * v, y]];
    });
    for (let col = 0; col < 8; col++) {
      let pivot = col;
      for (let row = col + 1; row < 8; row++) {
        if (Math.abs(rows[row][col]) > Math.abs(rows[pivot][col])) pivot = row;
      }
      [rows[col], rows[pivot]] = [rows[pivot], rows[col]];
      const divisor = rows[col][col];
      for (let j = col; j <= 8; j++) rows[col][j] /= divisor;
      for (let row = 0; row < 8; row++) {
        if (row === col) continue;
        const factor = rows[row][col];
        for (let j = col; j <= 8; j++) rows[row][j] -= factor * rows[col][j];
      }
    }
    const h = rows.map(row => row[8]);
    const projection = new DOMMatrix([h[0], h[3], 0, h[6], h[1], h[4], 0, h[7], 0, 0, 1, 0, h[2], h[5], 0, 1]);
    const viewerStyle = getComputedStyle(viewerImage);
    const viewerWidth = parseFloat(viewerStyle.width), viewerHeight = parseFloat(viewerStyle.height);
    return new DOMMatrix().translate(-viewer.clientWidth / 2, -viewer.clientHeight / 2)
      .multiply(projection).translate(.5, .5).scale(1 / viewerWidth, 1 / viewerHeight).toString();
  }
  addEventListener('resize', () => {
    if (viewer.open) {
      sizeViewer();
      const card = cards.get(viewingIndex);
      if (card) fitImage(card.querySelector('img'), card);
    }
  });
  function openArtwork(index) {
    const card = cards.get(index);
    if (!card || viewer.open) return;
    const source = card.querySelector('img');
    if (!source.naturalWidth) return;
    returnFocus = document.activeElement;
    viewingIndex = index;
    travel = null;
    target = position; velocity = inputVelocity = 0;
    if (frame) cancelAnimationFrame(frame);
    frame = 0; previousTime = 0;
    viewerImage.src = artworks[index].url;
    viewerImage.alt = artworks[index].title;
    document.querySelector('#viewer-title').textContent = artworks[index].title;
    const ratio = source.naturalWidth / source.naturalHeight;
    const height = Math.min(innerHeight, innerWidth * .94 / ratio);
    viewerImage.style.height = `${height}px`;
    viewerImage.style.width = `${height * ratio}px`;
    viewer.showModal();
    card.classList.add('viewing');
    sourceAnimation = source.animate([{ opacity: getComputedStyle(source).opacity }, { opacity: 0 }], { duration: reduced.matches ? 0 : 220, fill: 'forwards' });
    if (!reduced.matches) {
      viewerAnimation = viewerImage.animate([
        { transform: stackTransform(), opacity: 0 },
        { transform: 'none', opacity: 1 }
      ], { duration: 850, easing: 'cubic-bezier(.18, .7, .2, 1)', fill: 'both' });
      backdropAnimation = viewerBackground.animate([{ opacity: 0 }, { opacity: .94 }],
        { duration: 650, easing: 'ease-out', fill: 'both' });
    }
  }
  async function closeArtwork() {
    if (closingViewer || !viewer.open) return;
    closingViewer = true;
    const startTransform = getComputedStyle(viewerImage).transform;
    const startOpacity = getComputedStyle(viewerImage).opacity;
    const backgroundOpacity = getComputedStyle(viewerBackground).opacity;
    viewerAnimation?.cancel(); backdropAnimation?.cancel();
    const card = cards.get(viewingIndex);
    if (card && !reduced.matches) {
      const returnTransform = stackTransform();
      sourceAnimation?.cancel();
      sourceAnimation = card.querySelector('img').animate([{ opacity: 0 }, { opacity: 1 }], { delay: 700, duration: 250, fill: 'both' });
      viewerAnimation = viewerImage.animate([
        { transform: startTransform, opacity: startOpacity },
        { transform: returnTransform, opacity: Number(card.style.opacity), offset: .86 },
        { transform: returnTransform, opacity: 0 }
      ], { duration: 950, easing: 'cubic-bezier(.2, .65, .25, 1)', fill: 'both' });
      backdropAnimation = viewerBackground.animate([{ opacity: backgroundOpacity }, { opacity: 0 }],
        { duration: 850, easing: 'ease-out', fill: 'both' });
      await viewerAnimation.finished.catch(() => {});
    }
    sourceAnimation?.cancel();
    card?.classList.remove('viewing');
    viewer.close();
    viewerAnimation?.cancel(); backdropAnimation?.cancel();
    viewerImage.removeAttribute('src');
    closingViewer = false; viewingIndex = null;
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true }); else stage.focus({ preventScroll: true });
    // Keep the stack at exactly the pose we returned to. New input resumes movement.
    target = landing = position; velocity = inputVelocity = 0;
    lastInput = performance.now() - 1000; wake();
  }
  viewer.addEventListener('cancel', event => { event.preventDefault(); closeArtwork(); });
  viewer.addEventListener('click', closeArtwork);
  let artworks = [], position = 0, target = 0, lastInput = 0, frame = 0, previousTime = 0, selected = -1, pointer = null;
  const clamp = value => Math.max(0, Math.min(artworks.length - 1, value));
  const period = item => item.year === null ? 'undated' : `${Math.floor(item.year / 100) * 100}s`;
  function stopTravel() {
    if (!travel) return;
    travel = null; target = position; velocity = inputVelocity = 0; landing = null;
  }
  function move(value, mode = motionMode) {
    stopTravel();
    motionMode = mode;
    target = clamp(value);
    lastInput = performance.now();
    landing = null;
    wake();
  }
  function wake() { if (!artworks.length || viewer.open) return; if (!frame) frame = requestAnimationFrame(animate); }
  function makeCard(index) {
    const item = artworks[index];
    const card = document.createElement('article');
    card.className = 'artwork';
    card.dataset.index = index;
    const plane = document.createElement('div'); plane.className = 'plane';
    plane.setAttribute('role', 'button'); plane.tabIndex = -1;
    plane.setAttribute('aria-label', `Enlarge ${item.title}`);
    plane.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); openArtwork(index); }
    });
    const image = document.createElement('img'); image.alt = item.title; image.decoding = 'async';
    image.addEventListener('load', () => {
      fitImage(image, card);
      plane.classList.add('loaded');
    }, { once: true });
    image.addEventListener('error', () => {
      image.hidden = true;
      const note = document.createElement('span'); note.className = 'unavailable'; note.textContent = 'image unavailable'; plane.append(note);
    }, { once: true });
    plane.append(image);
    const century = document.createElement('div'); century.className = 'period'; century.textContent = period(item);
    const caption = document.createElement('div'); caption.className = 'caption'; caption.textContent = item.title;
    const date = document.createElement('small');
    date.textContent = item.year === null ? 'date unknown' : item.precision === 'century' ? 'century approximate' : String(item.year);
    caption.append(date); card.append(plane, century, caption); scene.append(card);
    cards.set(index, card);
    return card;
  }
  function render() {
    const nearest = Math.round(position);
    // A bounded depth window: only these few cards can exist, regardless of archive size.
    const visible = new Set();
    for (let i = Math.max(0, Math.ceil(position - 1.15)); i <= Math.min(artworks.length - 1, Math.floor(position + 3.2)); i++) {
      if (reduced.matches && i !== nearest) continue;
      const distance = i - position;
      const card = cards.get(i) || makeCard(i);
      fitImage(card.querySelector('img'), card);
      card.querySelector('.plane').tabIndex = i === nearest ? 0 : -1;
      const z = -distance * 470;
      const y = -distance * stage.clientHeight * .29;
      card.style.transform = reduced.matches ? 'translate(-50%, -50%)' : `translate(-50%, -50%) translate3d(0, ${y}px, ${z}px)`;
      const edge = Math.min(1, (distance + 1.15) / .3, (3.2 - distance) / .4);
      card.style.opacity = Math.max(0, edge * (.38 + .62 * Math.exp(-Math.abs(distance) * 4)));
      card.style.zIndex = String(100 - Math.round(Math.abs(distance) * 10));
      const rect = card.getBoundingClientRect();
      const viewport = stage.getBoundingClientRect();
      const intersects = rect.bottom > viewport.top && rect.top < viewport.bottom && rect.right > 0 && rect.left < innerWidth;
      card.style.visibility = intersects ? 'visible' : 'hidden';
      if (intersects) {
        visible.add(i);
        const image = card.querySelector('img');
        // Attach an image source only after its projected card enters the viewport.
        if (!image.hasAttribute('src') && Math.abs(velocity) < 12) image.src = artworks[i].url;
      } else { card.remove(); cards.delete(i); }
    }
    for (const [index, card] of cards) {
      if (!visible.has(index)) { card.querySelector('img').removeAttribute('src'); card.remove(); cards.delete(index); }
    }
    scrub.value = nearest;
    if (selected !== nearest) {
      selected = nearest;
      const item = artworks[nearest];
      document.querySelector('#position').textContent = `${nearest + 1} / ${artworks.length.toLocaleString()}`;
      const open = document.querySelector('#open'); open.href = item.url; open.hidden = false;
      scrub.setAttribute('aria-valuetext', `${item.title}, ${period(item)}`);
      document.querySelector('#previous').disabled = nearest === 0;
      document.querySelector('#next').disabled = nearest === artworks.length - 1;
      document.querySelectorAll('#centuries button').forEach(button => button.setAttribute('aria-current', String(button.textContent === period(item))));
    }
  }
  function animate(now) {
    frame = 0;
    const elapsed = Math.min(40, now - (previousTime || now - 16)); previousTime = now;
    if (travel) {
      if (travel.start === null) travel.start = now;
      const u = Math.min(1, (now - travel.start) / travel.duration);
      const ease = u * u * u * (10 + u * (-15 + 6 * u));
      const nextPosition = travel.from + (travel.to - travel.from) * ease;
      velocity = (nextPosition - position) / Math.max(.001, elapsed / 1000);
      position = target = nextPosition;
      if (u === 1) { travel = null; velocity = inputVelocity = 0; landing = position; lastInput = now - 1000; }
      render(); wake(); return;
    }
    const idle = now - lastInput;
    const settling = idle > 140 && !pointer;
    // Choose a projected resting point, then ease the moving target toward it.
    // No rounded-position jump or change of spring stiffness at release.
    if (settling) {
      if (landing === null) landing = Math.round(clamp(target + inputVelocity * .14));
      target = clamp(target + inputVelocity * elapsed / 1000);
      inputVelocity *= Math.exp(-elapsed / 145);
      const attraction = Math.min(1, Math.max(0, (idle - 140) / 420));
      target += (landing - target) * (1 - Math.exp(-elapsed * attraction / 420));
    }
    if (reduced.matches) {
      position = target = landing === null ? target : landing;
      velocity = inputVelocity = 0;
    } else {
      // Small integration steps keep the damped spring consistent at any refresh rate.
      for (let remaining = elapsed / 1000; remaining > 0;) {
        const dt = Math.min(remaining, 1 / 120); remaining -= dt;
        const destination = target;
        const desiredFrequency = motionMode === 'keys' ? 5.5 : pointer ? 9 : 7;
        springFrequency += (desiredFrequency - springFrequency) * (1 - Math.exp(-dt / .2));
        const frequency = springFrequency;
        velocity += ((destination - position) * frequency * frequency - 2 * frequency * velocity) * dt;
        position = clamp(position + velocity * dt);
        if ((position === 0 && velocity < 0) || (position === artworks.length - 1 && velocity > 0)) velocity = 0;
      }
    }
    const destination = landing === null ? target : landing;
    const resting = settling && landing !== null && Math.abs(destination - position) < .00005 && Math.abs(velocity) < .0005;
    // Avoid forcing the final fraction of a pixel to an integer position. That
    // correction was the visible bump at the end of a glide.
    if (resting) { target = position; velocity = inputVelocity = 0; }
    render();
    if (!resting) wake();
    else {
      previousTime = 0;
      document.querySelector('#announcement').textContent = `${artworks[selected].title}, ${period(artworks[selected])}`;
    }
  }

  stage.addEventListener('wheel', event => {
    if (!artworks.length || event.ctrlKey) return;
    event.preventDefault();
    const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? stage.clientHeight : 1);
    stopTravel();
    const now = performance.now();
    // Reverse the deck direction: moving the page down moves the archive back,
    // while moving up brings later artworks forward.
    const delta = -pixels / 300;
    const interval = Math.max(16, Math.min(100, now - (lastWheel || now - 50)));
    if (now - lastWheel > 180) inputVelocity = 0;
    // A Mac trackpad already sends its own inertial tail. Adding another one
    // made the deck feel detached. Only discrete line-wheel input gets a small
    // synthetic coast; touch releases keep their own measured velocity.
    if (event.deltaMode === 0) {
      inputVelocity = 0;
    } else {
      inputVelocity = inputVelocity * .45 + delta / interval * 1000 * .55;
      inputVelocity = Math.max(-12, Math.min(12, inputVelocity));
    }
    lastWheel = now;
    if (landing !== null) target = position;
    move(target + delta, 'wheel');
  }, { passive: false });
  stage.addEventListener('pointerdown', event => {
    if (!artworks.length || event.button !== 0) return;
    stopTravel();
    pointer = { id: event.pointerId, y: event.clientY, startX: event.clientX, startY: event.clientY,
      card: event.target.closest('.artwork'), moved: false, time: performance.now(), velocity: 0 };
    inputVelocity = 0; landing = null; motionMode = 'drag';
    target = position; stage.setPointerCapture(event.pointerId);
  });
  stage.addEventListener('pointermove', event => {
    if (!pointer || pointer.id !== event.pointerId) return;
    if (Math.hypot(event.clientX - pointer.startX, event.clientY - pointer.startY) > 6) pointer.moved = true;
    if (!pointer.moved) return;
    const now = performance.now(), delta = (event.clientY - pointer.y) / 220;
    pointer.velocity = pointer.velocity * .6 + delta / Math.max(8, now - pointer.time) * .4;
    move(target + delta); pointer.y = event.clientY; pointer.time = now;
  });
  function release(event) {
    if (!pointer || pointer.id !== event.pointerId) return;
    const clicked = !pointer.moved && pointer.card;
    inputVelocity = performance.now() - pointer.time < 90 ? Math.max(-18, Math.min(18, pointer.velocity * 1000)) : 0;
    pointer = null;
    if (clicked) openArtwork(Number(clicked.dataset.index));
    move(target);
  }
  stage.addEventListener('pointerup', release);
  stage.addEventListener('pointercancel', () => { pointer = null; wake(); });
  function stepArtwork(amount) {
    stopTravel();
    const destination = Math.round(landing ?? target) + amount;
    inputVelocity = 0;
    move(destination, 'keys');
    landing = target;
  }
  document.addEventListener('keydown', event => {
    if (!artworks.length || viewer.open || event.target.matches('input, textarea, select, [contenteditable]')) return;
    const actions = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1, PageDown: 10, PageUp: -10 };
    if (event.key in actions) { event.preventDefault(); stepArtwork(actions[event.key]); }
    if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); jump(event.key === 'Home' ? 0 : artworks.length - 1); }
  });
  document.querySelector('#previous').onclick = () => stepArtwork(-1);
  document.querySelector('#next').onclick = () => stepArtwork(1);
  // Long-distance jumps start at the destination, avoiding requests for every intervening work.
  function jump(index) { stopTravel(); velocity = inputVelocity = 0; position = target = Number(index); move(position); }
  function travelTo(index) {
    stopTravel();
    if (reduced.matches) { jump(index); return; }
    const distance = Math.abs(index - position);
    if (distance < .01) return;
    travel = { from: position, to: index, start: null, duration: Math.min(3200, 1100 + Math.log1p(distance) * 230) };
    velocity = inputVelocity = 0; landing = null;
    wake();
  }
  scrub.addEventListener('input' , () => jump(scrub.value));
  addEventListener('resize', wake);
  reduced.addEventListener('change', wake);
  fetch('assets/timeline/artworks.json').then(response => {
    if (!response.ok) throw new Error('Archive unavailable');
    return response.json();
  }).then(items => {
    if (!items.length) throw new Error('Empty archive');
    artworks = items.filter(item => item.year === null || item.year >= 1200); scrub.max = artworks.length - 1;
    const periods = new Set();
    artworks.forEach((item, index) => {
      const label = period(item);
      if (periods.has(label)) return;
      periods.add(label);
      const button = document.createElement('button'); button.textContent = label;
      button.onclick = () => travelTo(index);
      const navigation = document.querySelector('#centuries');
      if (navigation.childNodes.length) navigation.append(document.createTextNode(' / '));
      navigation.append(button);
    });
    message.hidden = true; wake();
  }).catch(() => {
    message.textContent = 'The archive could not load. Please refresh, or browse the art archive.';
    const link = document.createElement('a'); link.href = 'art.html'; link.textContent = ' open archive'; message.append(link);
  });
})();
