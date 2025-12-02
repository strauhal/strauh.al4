document.addEventListener('DOMContentLoaded', () => {

    /**
     * CONFIGURATION
     * Adjusted timings for optimal responsiveness vs. resource usage.
     */
    const CONFIG = {
        DESKTOP_HOVER_DELAY: 40,  // ms: Just enough to skip accidental swipes
        MOBILE_SCROLL_DELAY: 100, // ms: Snappier mobile response
        CACHE_SIZE: 50,
        DEFAULT_ANCHOR_Y: 10,
        IMG_EXTS: ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    };

    /**
     * CENTRAL STATE MANAGEMENT
     * Single source of truth for all interactions.
     */
    const state = {
        isMobile: () => window.matchMedia("(max-width: 900px)").matches,
        needsLayoutUpdate: true,
        linkPositions: [], 
        stickyLink: null,
        anchorY: CONFIG.DEFAULT_ANCHOR_Y,
        lastTapped: null,
        allowClick: false,
        activeImgSrc: null, // The "Conductor's Baton" - dictates what plays
        timers: { hover: null, load: null },
        scrollTicking: false
    };

    // Construct optimized selector string once
    const LINK_SELECTOR = CONFIG.IMG_EXTS
        .flatMap(ext => [ext, ext.toUpperCase()])
        .map(ext => `a[href$="${ext}"]`)
        .join(', ');

    /**
     * MODULE: YouTube Embeds
     * Handles text-to-iframe conversion with toggle functionality.
     */
    function initYouTubeEmbeds() {
        const paragraphs = document.querySelectorAll('p');
        const youtubeRegex = /(https?:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]+))(?:&t=(\d+)s)?/;

        paragraphs.forEach(p => {
            const match = youtubeRegex.exec(p.innerHTML);
            if (!match) return;

            const [fullUrl, _, videoId, startTime] = match;

            // Linkify text URL if plain text
            if (!p.querySelector(`a[href="${fullUrl}"]`)) {
                p.innerHTML = p.innerHTML.replace(fullUrl, `<a href="${fullUrl}" target="_blank">${fullUrl}</a>`);
            }
            
            const embedLink = document.createElement('a');
            Object.assign(embedLink.style, {
                cursor: 'pointer', marginLeft: '5px', textDecoration: 'underline'
            });
            embedLink.textContent = '[display]';

            const container = document.createElement('div');
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
                
                // Content shift invalidates layout cache
                state.needsLayoutUpdate = true;
            });
        });
    }

    /**
     * MODULE: Image Preview
     * Handles all image interaction logic.
     */
    function initImagePreview() {
        // --- 1. DOM Construction ---
        const container = document.createElement('div');
        container.id = 'image-preview-container';
        
        Object.assign(container.style, {
            position: 'fixed', top: '0', left: '0', width: '100vw', height: '100vh',
            zIndex: '-1', pointerEvents: 'none', display: 'none',
            flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            transform: 'translate3d(0, 0, 0)', // Hardware Accel
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
                // LRU: Re-insert to update order
                const val = imageCache.get(src);
                imageCache.delete(src);
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
            state.linkPositions = Array.from(imageLinks).map(link => ({
                link,
                top: link.getBoundingClientRect().top + scrollY
            }));
            state.needsLayoutUpdate = false;
        };

        // --- 4. Visual Logic ---
        
        const clearHighlights = () => {
            document.querySelectorAll('.mobile-hover').forEach(el => el.classList.remove('mobile-hover'));
        };

        const updatePreview = (src) => {
            // Set the "current note" immediately
            state.activeImgSrc = src;

            const cached = getCachedImage(src);
            
            // Prepare container
            container.style.display = 'flex';
            container.style.zIndex = '-1';
            img.style.display = 'none'; 

            // Apply styles
            Object.assign(img.style, {
                width: 'auto', height: 'auto',
                maxWidth: '100%', maxHeight: '100%', 
                objectFit: 'contain'
            });

            const render = () => {
                // STRICT CHECK: Is this still the active image?
                if (state.activeImgSrc !== src) return;

                if (img.src !== cached.src) img.src = cached.src;
                img.style.display = 'block';
            };

            if (cached.complete) render();
            else cached.onload = render;
        };

        const hidePreview = () => {
            state.activeImgSrc = null;
            container.style.display = 'none';
            img.src = ''; // Cancel/Clear
            clearHighlights();
        };

        // --- 5. Mobile Scroll Logic ---

        const updateStickyHighlight = (force = false) => {
            if (state.needsLayoutUpdate) recalculateLayout();

            const targetY = window.scrollY + state.anchorY;
            let closest = null;
            let minDiff = Infinity;

            // Fast Array Scan (O(n))
            for (const item of state.linkPositions) {
                const diff = Math.abs(item.top - targetY);
                if (diff < minDiff) {
                    minDiff = diff;
                    closest = item.link;
                }
            }

            if (closest && (closest !== state.stickyLink || force)) {
                clearHighlights();
                state.stickyLink = closest;
                state.stickyLink.classList.add('mobile-hover');

                clearTimeout(state.timers.load);
                state.timers.load = setTimeout(() => {
                    if (state.stickyLink) updatePreview(state.stickyLink.href);
                }, CONFIG.MOBILE_SCROLL_DELAY);
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

        // --- 6. Event Delegation (The Conductor) ---

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

            if (!state.isMobile()) return; // Desktop = Follow Link

            // Mobile Double-Tap Logic
            if (state.allowClick && state.lastTapped === link) {
                state.allowClick = false;
                return; // Follow Link
            }
            e.preventDefault(); // Block Link
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
            if (!state.stickyLink) ensureMobileInit();

            const link = e.target.closest(LINK_SELECTOR);

            if (link) {
                state.anchorY = e.touches[0].clientY;

                if (link === state.lastTapped) {
                    state.allowClick = true;
                } else {
                    state.allowClick = false;
                    state.lastTapped = link;
                    
                    // Immediate Feedback
                    clearHighlights();
                    state.stickyLink = link;
                    state.stickyLink.classList.add('mobile-hover');
                    clearTimeout(state.timers.load);
                    updatePreview(state.stickyLink.href);
                }
            } else {
                updateStickyHighlight(false);
            }
        }, { passive: true });

        // Mobile Touch End (Clean up any ghost highlights)
        document.body.addEventListener('touchend', () => {
            if (!state.isMobile()) return;
            updateStickyHighlight(true);
        }, { passive: true });

        // Resize / Orientation Change
        window.addEventListener('resize', () => {
            state.needsLayoutUpdate = true;
            if (state.isMobile()) {
                ensureMobileInit();
            } else {
                // Reset mobile state if entering desktop mode
                if (state.stickyLink) {
                    state.stickyLink = null;
                    hidePreview();
                }
            }
        });

        // CRITICAL: Final Layout Tune-up
        window.addEventListener('load', () => {
            recalculateLayout();
            if (state.isMobile()) ensureMobileInit();
        });

        // Start
        recalculateLayout();
        if (state.isMobile()) ensureMobileInit();
    }

    initYouTubeEmbeds();
    initImagePreview();
});