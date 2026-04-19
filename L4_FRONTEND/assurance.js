// =============================================================================
// CellRoute - Closed-Loop Network Assurance Engine (assurance.js)
// =============================================================================
console.log("> [CellRoute] assurance.js v2.4 Initializing...");

// This module implements the self-healing demo flow:
//   1. User clicks "Simulate Outage"
//   2. A pulsing red dead-zone appears on the map along the current route
//   3. The "LIVE FEED" status switches to "Network Failure Detected" (Red)
//   4. UI shows "Autonomous Recovery in Progress..."
//   5. System "re-calculates" (or fetches the best signal route)
//   6. Route is updated on map, and status returns to "Active"

let outageZoneLayers = [];
let isRecovering = false;

function triggerOutage() {
    if (currentRoutes.length === 0 || !startMarker || !endMarker) {
        alert("Please load a route first (e.g., Demo Route).");
        return;
    }

    const btn = document.getElementById('btn-outage');
    const recoverBtn = document.getElementById('btn-recover');
    btn.style.display = 'none';
    if (recoverBtn) recoverBtn.style.display = 'block';

    // Update Status Badge
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');
    if (statusDot) statusDot.style.background = '#ef4444';
    if (statusText) statusText.innerHTML = 'NETWORK FAILURE DETECTED <span style="font-size:10px; opacity:0.7;">(SIMULATED)</span>';

    // Draw Outage Zone
    const currentRoute = currentRoutes[selectedRouteIndex];
    const latlngs = decodePolyline(currentRoute.geometry);
    const midpoint = latlngs[Math.floor(latlngs.length / 2)];

    const zone = L.circle(midpoint, {
        color: '#ef4444',
        fillColor: '#ef4444',
        fillOpacity: 0.2,
        radius: 800,
        className: 'outage-pulse'
    }).addTo(map);

    zone.bindTooltip("<b>SIGNAL DEAD ZONE</b>", { permanent: true, direction: 'center', className: 'outage-tooltip' });
    outageZoneLayers.push(zone);

    // Update Telemetry Chart
    if (window.telemetryChart) {
        window.telemetryChart.data.datasets[0].borderColor = '#ef4444';
        window.telemetryChart.update();
    }

    // Start Recovery Sequence
    setTimeout(startRecovery, 2000);
}

function startRecovery() {
    isRecovering = true;
    const statusText = document.querySelector('.status-text');
    if (statusText) statusText.innerHTML = 'AUTONOMOUS RECOVERY IN PROGRESS...';

    // Logic: Force the "Best Signal" route even if current bias is for eta
    // We do this by setting alpha to 1.0 and re-fetching
    const alphaSlider = document.getElementById('alpha-slider');
    const alphaDisplay = document.getElementById('alpha-display');
    if (alphaSlider) alphaSlider.value = 1.0;
    if (alphaDisplay) alphaDisplay.textContent = "1.0";

    // Re-fetch
    fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), 1.0);
}

function recoverOutage() {
    clearOutageZone();
    const btn = document.getElementById('btn-outage');
    const recoverBtn = document.getElementById('btn-recover');
    if (btn) btn.style.display = 'block';
    if (recoverBtn) recoverBtn.style.display = 'none';

    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');
    if (statusDot) statusDot.style.background = '#10b981';
    if (statusText) statusText.textContent = 'LIVE FEED: Active (4G/5G Hybrid)';

    if (window.telemetryChart) {
        window.telemetryChart.data.datasets[0].borderColor = '#10b981';
        window.telemetryChart.update();
    }
    isRecovering = false;
}

function clearOutageZone() {
    outageZoneLayers.forEach(l => map.removeLayer(l));
    outageZoneLayers = [];
}

// Attach listeners
document.addEventListener('DOMContentLoaded', () => {
    const btnOutage = document.getElementById('btn-outage');
    const btnRecover = document.getElementById('btn-recover');
    if (btnOutage) btnOutage.addEventListener('click', triggerOutage);
    if (btnRecover) btnRecover.addEventListener('click', recoverOutage);
});
