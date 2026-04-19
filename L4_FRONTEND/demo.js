// =============================================================================
// CellRoute - Guided Pitch / Demo Autopilot (demo.js)
// =============================================================================

function showPitchOverlay(stepName) {
    const overlay = document.createElement('div');
    overlay.className = 'pitch-overlay';
    overlay.innerHTML = `
        <div class="pitch-content">
            <h3>Demonstration Step</h3>
            <p>${stepName}</p>
        </div>
    `;
    document.body.appendChild(overlay);
    setTimeout(() => overlay.remove(), 3000);
}
