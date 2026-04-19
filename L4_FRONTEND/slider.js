const slider = document.getElementById('alpha-slider');
const display = document.getElementById('alpha-display');

// Debounce timer for slider to avoid spamming the API
let debounceTimer;

slider.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value).toFixed(1);
    display.textContent = val;
});

slider.addEventListener('change', (e) => {
    const alpha = parseFloat(e.target.value);
    
    if (startMarker && endMarker) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
        }, 300); // 300ms debounce
    }
});
