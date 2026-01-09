document.addEventListener('DOMContentLoaded', () => {

    /**
     * CONFIGURATION
     * Adjusted timings for optimal responsiveness vs. resource usage.
     */
    const CONFIG = {
        DESKTOP_HOVER_DELAY: 40,  // ms: Just enough to skip accidental swipes
        MOBILE_SCROLL_DELAY: 100, // ms: Snappier response after scrolling stops
        CACHE_SIZE: 50,
        DEFAULT_ANCHOR_Y: 10,
        SCROLL_THRESHOLD: 10,     // px: Movement tolerance to distinguish tap vs scroll
        IMG_EXTS: ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    };

    /**
     * CENTRAL STATE MANAGEMENT
     * The single source of truth—our score.
     */
    const state = {
        isMobile: () => window.matchMedia("(max-width: 900px)").matches,
        needsLayoutUpdate: true,
        linkPositions: [], 
        stickyLink: null,
        anchorY: CONFIG.DEFAULT_ANCHOR_Y,
        lastTapped: null,
        allowClick: false,
        activeImgSrc: null, // The "Conductor's Baton" - tracks the currently requested image
        timers: { hover: null, load: null },
        scrollTicking: false,
        touchStartY: 0,     // Track touch start position
        isScrolling: false  // Track if user is scrolling
    };

    // Construct selector string efficiently once
    const LINK_SELECTOR = CONFIG.IMG_EXTS
        .flatMap(ext => [ext, ext.toUpperCase()])
        .map(ext => `a[href$="${ext}"]`)
        .join(', ');

    /**
     * MODULE: YouTube Embeds
     * Handles text-to-iframe conversion.
     */
    function initYouTubeEmbeds() {
        const paragraphs = document.querySelectorAll('p');
        const youtubeRegex = /(https?:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]+))(?:&t=(\d+)s)?/;

        paragraphs.forEach(p => {
            const match = youtubeRegex.exec(p.innerHTML);
            if (!match) return;

            const [fullUrl, _, videoId, startTime] = match;

            // Linkify plain text URL if needed
            if (!p.querySelector(`a[href="${fullUrl}"]`)) {
                p.innerHTML = p.innerHTML.replace(fullUrl, `<a href="${fullUrl}" target="_blank">${fullUrl}</a>`);
            }
            
            const embedLink = document.createElement('a');
            Object.assign(embedLink.style, {
                cursor: 'pointer', marginLeft: '5px', textDecoration: 'underline'
            });
            embedLink.textContent = '[display]';

            const container = document.createElement('div');
            
            // Append elements securely
            p.appendChild(embedLink);
            p.appendChild(container);

            let isOpen = false;

            embedLink.addEventListener('click', (e) => {
                e.preventDefault();
                isOpen = !isOpen;

                if (isOpen) {
                    container.innerHTML = `
                        <br>
                        <iframe width="560" height="315" frameborder="0" 
                            src="https://www.youtube.com/embed/${videoId}?autoplay=1${startTime ? `&start=${startTime}` : ''}" 
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                            allowfullscreen style="margin-left:0">
                        </iframe>`;
                } else {
                    container.innerHTML = '';
                }
                
                // Layout changed, mark for recalc
                state.needsLayoutUpdate = true;
            });
        });
    }

    /**
     * MODULE: Image Preview
     * The visual performance logic.
     */
    function initImagePreview() {
        // --- 1. DOM Construction ---
        const container = document.createElement('div');
        container.id = 'image-preview-container';
        
        Object.assign(container.style, {
            position: 'fixed', top: '0', left: '0', width: '100vw', height: '100vh',
            zIndex: '-1', pointerEvents: 'none', display: 'none',
            flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            transform: 'translate3d(0, 0, 0)', // Hardware Acceleration
            webkitTransform: 'translate3d(0, 0, 0)',
            backfaceVisibility: 'hidden'
        });

        const img = document.createElement('img');
        Object.assign(img.style, { maxWidth: '100%', maxHeight: '100%' });
        
        container.appendChild(img);
        document.body.appendChild(container);

        // --- 2. Cache System ---
        const imageCache = new Map();
        
        const getCachedImage = (src) => {
            if (imageCache.has(src)) {
                const val = imageCache.get(src);
                imageCache.delete(src); // Refresh LRU position
                imageCache.set(src, val);
                return val;
            }
            
            const newImg = new Image();
            newImg.src = src;
            
            if (imageCache.size >= CONFIG.CACHE_SIZE) {
                imageCache.delete(imageCache.keys().next().value);
            }
            
            imageCache.set(src, newImg);
            return newImg;
        };

        // --- 3. Layout Caching ---
        const imageLinks = document.querySelectorAll(LINK_SELECTOR);

        const recalculateLayout = () => {
            const scrollY = window.scrollY;
            // Batch read to avoid layout thrashing
            state.linkPositions = Array.from(imageLinks).map(link => ({
                link,
                top: link.getBoundingClientRect().top + scrollY
            }));
            state.needsLayoutUpdate = false;
        };

        // --- 4. Visual Logic ---
        
        const clearHighlights = () => {
            const active = document.querySelectorAll('.mobile-hover');
            for (let i = 0; i < active.length; i++) active[i].classList.remove('mobile-hover');
        };

        const updatePreview = (src) => {
            // "The Baton": Mark this specific request as active
            state.activeImgSrc = src;

            const cached = getCachedImage(src);
            
            container.style.display = 'flex';
            container.style.zIndex = '-1';
            img.style.display = 'none'; 

            Object.assign(img.style, {
                width: 'auto', height: 'auto',
                maxWidth: '100%', maxHeight: '100%', 
                objectFit: 'contain'
            });

            const render = () => {
                // Strict Synchronization: If the conductor moved on, silence this note.
                if (state.activeImgSrc !== src) return;

                if (img.src !== cached.src) img.src = cached.src;
                img.style.display = 'block';
            };

            if (cached.complete) render();
            else cached.onload = render;
        };

        const hidePreview = () => {
            state.activeImgSrc = null; // Drop the baton
            container.style.display = 'none';
            img.src = ''; // Clear buffer
            clearHighlights();
        };

        // --- 5. Mobile Scroll Logic ---

        const updateStickyHighlight = (force = false) => {
            if (state.needsLayoutUpdate) recalculateLayout();

            const targetY = window.scrollY + state.anchorY;
            let closest = null;
            let minDiff = Infinity;

            // Efficient linear scan (O(n))
            for (let i = 0; i < state.linkPositions.length; i++) {
                const item = state.linkPositions[i];
                const diff = Math.abs(item.top - targetY);
                if (diff < minDiff) {
                    minDiff = diff;
                    closest = item.link;
                }
            }

            // Persistence Logic:
            // Only switch highlight if we found a NEW valid link OR if forced (tap)
            if (closest && (closest !== state.stickyLink || force)) {
                clearHighlights();
                state.stickyLink = closest;
                state.stickyLink.classList.add('mobile-hover');

                clearTimeout(state.timers.load);
                state.timers.load = setTimeout(() => {
                    if (state.stickyLink) updatePreview(state.stickyLink.href);
                }, CONFIG.MOBILE_SCROLL_DELAY);
            } 
            // CRITICAL: Ensure the current sticky link stays lit if no better link is found
            else if (state.stickyLink) {
                if (!state.stickyLink.classList.contains('mobile-hover')) {
                    state.stickyLink.classList.add('mobile-hover');
                }
            }
            state.scrollTicking = false;
        };

        const ensureMobileInit = () => {
            if (state.needsLayoutUpdate) recalculateLayout();
            if (!state.stickyLink && imageLinks.length > 0) {
                state.anchorY = CONFIG.DEFAULT_ANCHOR_Y;
                state.stickyLink = imageLinks[0];
                state.stickyLink.classList.add('mobile-hover');
                updatePreview(state.stickyLink.href);
            }
        };

        // --- 6. Event Delegation ---

        // Desktop Hover
        document.body.addEventListener('mouseover', (e) => {
            if (state.isMobile()) return;
            const link = e.target.closest(LINK_SELECTOR);
            
            if (link) {
                clearTimeout(state.timers.hover);
                state.timers.hover = setTimeout(() => {
                    clearHighlights();
                    link.classList.add('mobile-hover');
                    updatePreview(link.href);
                }, CONFIG.DESKTOP_HOVER_DELAY);
            }
        }, { passive: true });

        // Desktop Leave
        document.body.addEventListener('mouseout', (e) => {
            if (state.isMobile()) return;
            const link = e.target.closest(LINK_SELECTOR);
            if (link) {
                clearTimeout(state.timers.hover);
                hidePreview();
            }
        }, { passive: true });

        // Click Guard
        document.body.addEventListener('click', (e) => {
            const link = e.target.closest(LINK_SELECTOR);
            if (!link) return;

            if (!state.isMobile()) return; 

            // Mobile Double-Tap
            if (state.allowClick && state.lastTapped === link) {
                state.allowClick = false;
                return; 
            }
            e.preventDefault();
        });

        // Mobile Scroll
        window.addEventListener('scroll', () => {
            if (!state.isMobile()) return;
            
            if (!state.stickyLink) ensureMobileInit();

            if (!state.scrollTicking) {
                window.requestAnimationFrame(() => updateStickyHighlight(false));
                state.scrollTicking = true;
            }
        }, { passive: true });

        // Mobile Touch Start
        document.body.addEventListener('touchstart', (e) => {
            if (!state.isMobile()) return;
            
            state.touchStartY = e.touches[0].clientY;
            state.isScrolling = false;

            if (!state.stickyLink) ensureMobileInit();
        }, { passive: true });

        // Mobile Touch Move - Detect Scroll Intent
        document.body.addEventListener('touchmove', (e) => {
            if (!state.isMobile()) return;
            
            const currentY = e.touches[0].clientY;
            if (Math.abs(currentY - state.touchStartY) > CONFIG.SCROLL_THRESHOLD) {
                state.isScrolling = true;
            }
        }, { passive: true });

        // Mobile Touch End
        document.body.addEventListener('touchend', (e) => {
            if (!state.isMobile()) return;

            // If user scrolled significantly, do NOT select a new link based on touch position.
            // Just ensure the CURRENT highlight remains robust.
            if (state.isScrolling) {
                if (state.stickyLink) state.stickyLink.classList.add('mobile-hover');
                return; 
            }

            // User did NOT scroll (Tap intent)
            const touchY = e.changedTouches[0].clientY;
            const targetElement = document.elementFromPoint(e.changedTouches[0].clientX, touchY);
            const link = targetElement ? targetElement.closest(LINK_SELECTOR) : null;

            if (link) {
                // Update anchor to exact tap position
                state.anchorY = touchY;

                if (link === state.lastTapped) {
                    state.allowClick = true;
                } else {
                    state.allowClick = false;
                    state.lastTapped = link;
                    
                    // Instant update on Tap
                    clearHighlights();
                    state.stickyLink = link;
                    state.stickyLink.classList.add('mobile-hover');
                    clearTimeout(state.timers.load);
                    updatePreview(state.stickyLink.href);
                }
            } else {
                // Tapped blank space - Just reinforce the current sticky link
                if (state.stickyLink) state.stickyLink.classList.add('mobile-hover');
            }
        }, { passive: true });

        // Resize / Orientation Change
        window.addEventListener('resize', () => {
            state.needsLayoutUpdate = true;
            if (state.isMobile()) {
                ensureMobileInit();
            } else {
                if (state.stickyLink) {
                    state.stickyLink = null;
                    hidePreview();
                }
            }
        });

        // CRITICAL: Final Layout Tune-up after full load
        // Ensures mobile highlights snap correctly once fonts/layout settle
        window.addEventListener('load', () => {
            recalculateLayout();
            if (state.isMobile()) ensureMobileInit();
        });

        // Initial Boot
        recalculateLayout();
        if (state.isMobile()) ensureMobileInit();
    }

    initYouTubeEmbeds();
    initImagePreview();
});