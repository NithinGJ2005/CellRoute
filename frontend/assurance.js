// ═══════════════════════════════════════════════════════════════════════════
// CellRoute — Closed-Loop Network Assurance Engine (Frontend)
// ═══════════════════════════════════════════════════════════════════════════
// This module implements the self-healing demo flow:
//   1. User clicks "Simulate Outage"
//   2. A pulsing red dead-zone appears on the map along the current route
//   3. A NETWORK ALARM banner fires in the HUD
//   4. The backend outage registry is populated
//   5. Routes are automatically re-fetched (they now detour around the zone)
//   6. User clicks "Recover" to clear the outage and auto-re-routes again

let outageZoneLayers = [];    // Leaflet layers for the dead zone visuals
let activeOutageId = null;    // Current outage ID from the backend
let outageLatLng = null;      // Outage coordinates for map rendering

const OUTAGE_RADIUS_M = 800;  // Default blast radius in metres

// ── Core Outage Flow ────────────────────────────────────────────────────────

async function triggerOutage() {
    if (!currentRoutes || currentRoutes.length === 0) {
        alert('Load a demo route first, then simulate an outage.');
        return;
    }

    // Pick the midpoint of the primary (selected) route for maximum visual impact
    const route = currentRoutes[selectedRouteIndex] || currentRoutes[0];
    const latlngs = decodePolyline(route.geometry);
    const midIdx = Math.floor(latlngs.length / 2);
    const midpoint = latlngs[midIdx];
    const lat = midpoint[0];
    const lon = midpoint[1];
    outageLatLng = L.latLng(lat, lon);

    // 1. Tell the backend
    try {
        const res = await fetch('/api/outage', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat, lon, radius_m: OUTAGE_RADIUS_M })
        });
        const data = await res.json();
        activeOutageId = data.outage.id;
    } catch (e) {
        console.error('Outage API failed:', e);
        return;
    }

    // 2. Draw the dead zone on the map
    drawOutageZone(outageLatLng, OUTAGE_RADIUS_M);

    // 3. Show the alarm banner
    showAlarm(lat.toFixed(4), lon.toFixed(4));

    // 4. Toggle buttons
    document.getElementById('btn-outage').style.display = 'none';
    document.getElementById('btn-recover').style.display = 'block';

    // 5. Wait 1.5s for dramatic effect, then auto-re-route (self-healing!)
    setTimeout(async () => {
        if (startMarker && endMarker) {
            // Simulate vehicle's current position (Point B) 70% of the way toward the outage zone
            const carPosIdx = Math.floor(midIdx * 0.7);
            if (latlngs[carPosIdx]) {
                const newStart = L.latLng(latlngs[carPosIdx][0], latlngs[carPosIdx][1]);
                startMarker.setLatLng(newStart);
                startMarker.bindPopup("<b>Current Vehicle Position</b>").openPopup();
            }

            const alpha = parseFloat(document.getElementById('alpha-slider').value);
            await fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
        }
    }, 1500);
}

async function recoverOutage() {
    // 1. Clear on backend
    if (activeOutageId) {
        try {
            await fetch('/api/outage/clear-all', { method: 'POST' });
        } catch (e) {
            console.error('Recovery API failed:', e);
        }
    }

    // 2. Remove dead zone layers from map
    clearOutageZone();

    // 3. Hide alarm
    hideAlarm();

    // 4. Toggle buttons back
    document.getElementById('btn-outage').style.display = 'block';
    document.getElementById('btn-recover').style.display = 'none';

    activeOutageId = null;
    outageLatLng = null;

    // 5. Re-route with the outage cleared (back to optimal)
    if (startMarker && endMarker) {
        const alpha = parseFloat(document.getElementById('alpha-slider').value);
        await fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
    }
}

// ── Map Visualization ───────────────────────────────────────────────────────

function drawOutageZone(center, radiusM) {
    clearOutageZone();

    // Static opaque red zone
    const deadZone = L.circle(center, {
        radius: radiusM,
        color: '#ef4444',
        fillColor: '#ef4444',
        fillOpacity: 0.18,
        weight: 2,
        dashArray: '8, 6',
    }).addTo(map);

    // Pulsing ripple ring (pure CSS animation via SVG overlay)
    const ripple = L.circle(center, {
        radius: radiusM,
        color: '#ef4444',
        fillColor: '#ef4444',
        fillOpacity: 0.0,
        weight: 3,
        className: 'outage-ripple',
    }).addTo(map);

    // Center skull/warning marker
    const warningIcon = L.divIcon({
        html: `<div style="
            width: 36px; height: 36px;
            background: rgba(239, 68, 68, 0.85);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 18px;
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.6), 0 0 40px rgba(239, 68, 68, 0.2);
            animation: blink 0.8s infinite alternate;
        ">⚠</div>`,
        className: '',
        iconSize: [36, 36],
        iconAnchor: [18, 18],
    });
    const warningMarker = L.marker(center, { icon: warningIcon }).addTo(map);

    // Tooltip on the zone
    deadZone.bindTooltip(
        `<b style="color:#ef4444">OUTAGE ZONE</b><br>` +
        `<span style="color:#fca5a5">Tower KPI breach detected</span><br>` +
        `<span style="color:#94a3b8">Radius: ${radiusM}m • Auto-healing active</span>`,
        {
            permanent: true,
            direction: 'top',
            className: 'last-mile-tooltip',
            offset: [0, -radiusM * 0.004],
        }
    );

    outageZoneLayers.push(deadZone, ripple, warningMarker);
}

function clearOutageZone() {
    outageZoneLayers.forEach(l => map.removeLayer(l));
    outageZoneLayers = [];
}

// ── Alarm Banner ────────────────────────────────────────────────────────────

function showAlarm(lat, lon) {
    const banner = document.getElementById('alarm-banner');
    const body = document.getElementById('alarm-body-text');
    body.innerHTML = `
        <strong>Nokia Assurance Center</strong> detected throughput breach at
        <strong>(${lat}, ${lon})</strong>.<br>
        Threshold: <strong>DL throughput &lt; 80%</strong> → Major Alarm raised.<br>
        <span style="color: #10b981;">▸ Automated recovery workflow started — re-routing vehicle...</span>
    `;
    banner.classList.add('active');
}

function hideAlarm() {
    document.getElementById('alarm-banner').classList.remove('active');
}

// ── Event Bindings ──────────────────────────────────────────────────────────

document.getElementById('btn-outage').addEventListener('click', triggerOutage);
document.getElementById('btn-recover').addEventListener('click', recoverOutage);
