console.log("[Image-Toolkit] Content script loaded on: " + window.location.href);

// Detect environment
const api = (typeof browser !== 'undefined') ? browser : chrome;

let turboMode = false;

// Function to update turbo status from storage
const updateTurboStatus = () => {
    const getStorage = (keys) => {
        return new Promise((resolve) => {
            if (typeof browser !== 'undefined') {
                api.storage.local.get(keys).then(resolve);
            } else {
                api.storage.local.get(keys, resolve);
            }
        });
    };

    getStorage(['turboMode']).then((result) => {
        turboMode = result.turboMode || false;
        console.log("[Image-Toolkit] Turbo Mode is: " + (turboMode ? "ENABLED" : "DISABLED"));
    });
};

// Initial check
updateTurboStatus();

// Listen for storage changes to update dynamically
api.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.turboMode) {
        turboMode = changes.turboMode.newValue;
        console.log("[Image-Toolkit] Turbo Mode changed to: " + (turboMode ? "ENABLED" : "DISABLED"));
    }
});

// Intercept all relevant pointer/touch events to prevent site logic (like zoom/pan)
const blockAndDownload = (e) => {
    if (!turboMode) return;

    // For mouse events, only handle main button (Left Click)
    if (e.type.startsWith('mouse') && e.button !== 0) return;

    // Use elementsFromPoint to find images even under overlays
    const elements = document.elementsFromPoint(e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0),
        e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0));
    let targetImage = null;

    for (const el of elements) {
        if (el.tagName === 'IMG' && el.src) {
            targetImage = el;
            break;
        }
    }

    if (targetImage) {
        console.log("[Image-Toolkit] Intercepted " + e.type + " on image: " + targetImage.src);

        // Stop the event from reaching the site's elements or bubbling up
        e.stopPropagation();
        e.stopImmediatePropagation();

        // For 'click', we also prevent default (to stop links/zoom) and trigger download
        if (e.type === 'click') {
            e.preventDefault();
            console.log("[Image-Toolkit] Triggering download for: " + targetImage.src);

            const msg = { action: 'download_image', src: targetImage.src };
            api.runtime.sendMessage(msg);
        }
    }
};

// Listen to all phases that might trigger site logic
const events = ['click', 'mousedown', 'mouseup', 'pointerdown', 'pointerup', 'touchstart', 'touchend'];
events.forEach(eventType => {
    document.addEventListener(eventType, blockAndDownload, { capture: true, passive: false });
});
