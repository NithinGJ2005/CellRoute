// Initialize Mapbox / Leaflet
// Using CartoDB Dark Matter for a sleek look
const map = L.map('map', {
    zoomControl: false // Move zoom control out of the way of our UI
}).setView([12.9716, 77.5946], 13); // Default to Bengaluru

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

L.control.zoom({
    position: 'bottomright'
}).addTo(map);

// Global State
let currentRoutes = [];
let selectedRouteIndex = 0;
let routeLayers = [];
let towerLayers = [];
let startMarker = null;
let endMarker = null;

// Custom Marker Icons
const startIcon = L.divIcon({
    html: `
        <div style="position: relative; width: 24px; height: 24px;">
            <div style="position: absolute; width: 100%; height: 100%; background: #10b981; border-radius: 50%; opacity: 0.3; animation: pulsar 2s infinite;"></div>
            <div style="position: absolute; top: 6px; left: 6px; width: 12px; height: 12px; background: #fff; border: 3px solid #10b981; border-radius: 50%; box-shadow: 0 0 10px #10b981;"></div>
        </div>
    `,
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
});

const endIcon = L.divIcon({
    html: `
        <div style="position: relative; width: 32px; height: 32px;">
            <div style="position: absolute; width: 100%; height: 100%; background: #ef4444; border-radius: 50%; opacity: 0.3; animation: pulsar 1.5s infinite;"></div>
            <div style="position: absolute; top: 8px; left: 8px; width: 16px; height: 16px; background: #fff; border: 4px solid #ef4444; border-radius: 50%; box-shadow: 0 0 15px #ef4444;"></div>
        </div>
    `,
    className: '',
    iconSize: [32, 32],
    iconAnchor: [16, 16]
});

// Real-time Hardware Monitoring (Network Information API)
function updateHardwareStats() {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn) {
        document.getElementById('conn-type').textContent = conn.effectiveType.toUpperCase();
        document.getElementById('conn-speed').textContent = conn.downlink;
        
        // Listen for real-time changes
        conn.onchange = updateHardwareStats;
    }
}
updateHardwareStats();

// NEW: Telemetry Initialization
function initTelemetry() {
    const ctx = document.getElementById('telemetry-chart')?.getContext('2d');
    if (!ctx) return;

    telemetryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Signal Quality',
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.4,
                data: []
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false }, tooltip: { enabled: true } },
            scales: {
                x: { display: false },
                y: { 
                    min: 0, max: 100,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                }
            }
        }
    });

    const fCtx = document.getElementById('forecast-chart')?.getContext('2d');
    forecastChart = new Chart(fCtx, {
        type: 'bar',
        data: {
            labels: ['00','02','04','06','08','10','12','14','16','18','20','22'],
            datasets: [{
                label: 'Score',
                backgroundColor: '#3b82f6',
                borderRadius: 4,
                data: []
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 9 } } },
                y: { 
                    min: 0, max: 100,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8', font: { size: 9 } }
                }
            }
        }
    });
}
document.addEventListener('DOMContentLoaded', initTelemetry);

// The backend endpoint — relative so it always hits the same server as the page
const API_URL = "/api/route";

// Global Route Cache for instant slider response
// Key: start-end-alpha-weather-edge-slice-time
const routeCache = new Map();

function getCacheKey(start, end, alpha, weather, edge, slice, time, isp) {
    // Round lat/lon slightly to allow for minor snapping differences
    const s = `${start.lat.toFixed(5)},${start.lng.toFixed(5)}`;
    const e = `${end.lat.toFixed(5)},${end.lng.toFixed(5)}`;
    return `${s}|${e}|${alpha}|${weather}|${edge}|${slice}|${time || 'live'}|${isp || 'all'}`;
}

async function fetchRoutes(start, end, alpha, isBackground = false) {
    if (!start || !end) return;

    // 1. Check Cache
    const edgeToggle = document.getElementById('edge-toggle');
    const edge = (edgeToggle && edgeToggle.checked) ? '0.8' : '0.0';
    const activeSliceBtn = document.querySelector('.slice-btn.active');
    const slice = activeSliceBtn ? activeSliceBtn.dataset.slice : 'default';
    const simTimeSelect = document.getElementById('sim-time-select');
    const time = simTimeSelect ? simTimeSelect.value : '';
    const weatherToggle = document.getElementById('weather-toggle');
    const weather = (weatherToggle && weatherToggle.checked) ? 'rain' : 'clear';
    const ispSelect = document.getElementById('isp-select');
    const isp = ispSelect ? ispSelect.value : 'all';

    const cacheKey = getCacheKey(start, end, alpha, weather, edge, slice, time, isp);
    if (routeCache.has(cacheKey)) {
        const cachedData = routeCache.get(cacheKey);
        currentRoutes = cachedData.routes;
        selectedRouteIndex = 0;
        renderRoutes();
        renderRouteList();
        return;
    }
    
    // Only show loader for foreground requests
    if (!isBackground) {
        document.getElementById('loader').classList.add('visible');
    }
    
    try {
        const url = new URL(API_URL, window.location.origin);
        url.searchParams.append('start_lat', start.lat);
        url.searchParams.append('start_lon', start.lng);
        url.searchParams.append('end_lat', end.lat);
        url.searchParams.append('end_lon', end.lng);
        url.searchParams.append('alpha', alpha);
        url.searchParams.append('edge_weight', edge);
        url.searchParams.append('slice', slice);
        if (time) url.searchParams.append('time', time);
        url.searchParams.append('weather', weather);
        url.searchParams.append('isp', isp);

        const response = await fetch(url);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(`API Error ${response.status}: ${err.detail || 'Unknown Error'}`);
        }
        
        const data = await response.json();
        
        // Save to cache
        routeCache.set(cacheKey, data);

        // Only update UI if this is the CURRENT target alpha or if not background
        const currentAlpha = parseFloat(document.getElementById('alpha-slider').value);
        if (!isBackground || Math.abs(currentAlpha - alpha) < 0.01) {
            currentRoutes = data.routes;
            selectedRouteIndex = 0;
            renderRoutes();
            renderRouteList();
        }
        
    } catch (error) {
        if (!isBackground) {
            console.error("Failed to fetch routes:", error);
            alert("Failed to calculate routes. Is the backend running?");
        }
    } finally {
        if (!isBackground) {
            document.getElementById('loader').classList.remove('visible');
        }
    }
}

/**
 * Pre-computes routes for discrete alpha steps in the background
 * for immediate response when the user slides.
 */
function preFetchRoutes(start, end) {
    if (!start || !end) return;
    const steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0];
    steps.forEach(a => {
        // Debounce background fetches slightly to avoid thundering herd on backend
        setTimeout(() => fetchRoutes(start, end, a, true), 50);
    });
}

function clearMap() {
    routeLayers.forEach(layer => map.removeLayer(layer));
    routeLayers = [];
}

function clearTowers() {
    towerLayers.forEach(layer => map.removeLayer(layer));
    towerLayers = [];
}

async function drawRealTowers() {
    clearTowers();
    
    try {
        const response = await fetch(new URL("/api/towers", window.location.origin));
        if (!response.ok) throw new Error("Failed to load towers");
        
        const data = await response.json();
        const towers = data.towers;
        
        towers.forEach(t => {
            let isEdge = t.has_edge_upf;
            let radio = t.radio || "LTE";
            let rad = t.range || 1000;
            
            // Map radio to colors
            let color = isEdge ? '#8b5cf6' : (radio === 'NR' ? '#10b981' : (radio === 'LTE' ? '#f59e0b' : '#ef4444'));
            
            const circle = L.circle([t.lat, t.lon], {
                color: color,
                fillColor: color,
                fillOpacity: 0.1,
                radius: rad * 0.35, // Visually shrink the circles so they don't overlap aggressively
                weight: 1
            }).addTo(map);
            
            const marker = L.circleMarker([t.lat, t.lon], {
                radius: 3,
                color: '#fff',
                fillColor: color,
                fillOpacity: 1
            }).addTo(map);
            
            marker.bindTooltip(`<b>${radio} Base Station</b><br>Range: ${rad}m<br>Edge UPF: ${isEdge}`, {direction: 'top'});
            
            towerLayers.push(circle, marker);
        });
    } catch (e) {
        console.error("Error drawing real towers:", e);
    }
}

function renderRoutes() {
    clearMap();
    if (!currentRoutes || currentRoutes.length === 0) return;
    
    // Pass 1: Draw unselected (Grey) routes first so they are at the bottom layer
    currentRoutes.forEach((route, i) => {
        if (i === selectedRouteIndex) return;
        
        const latlngs = decodePolyline(route.geometry);
        if (!latlngs || latlngs.length === 0) return;

        const altLine = L.polyline(latlngs, {
            color: '#94a3b8', // Consistent light grey
            weight: 5,
            opacity: 0.5,
            lineJoin: 'round'
        }).addTo(map);
        routeLayers.push(altLine);
    });

    // Pass 2: Draw the SELECTED route last so it stays on top
    const selectedRoute = currentRoutes[selectedRouteIndex];
    if (selectedRoute) {
        const latlngs = decodePolyline(selectedRoute.geometry);
        if (latlngs && latlngs.length > 0) {
            
            // Draw the HIGHLIGHT (Solid Orange)
            const primaryLine = L.polyline(latlngs, {
                color: '#f97316', // Vibrant Orange
                weight: 7,
                opacity: 1.0, 
                lineJoin: 'round'
            }).addTo(map);
            routeLayers.push(primaryLine);
            
            // Draw last-mile handoff in Orange
            const lastRoadPoint = latlngs[latlngs.length - 1];
            const finalDestination = endMarker.getLatLng();
            const lastMilePath = L.polyline([lastRoadPoint, finalDestination], {
                color: '#ea580c', // Darker Orange
                weight: 4,
                dashArray: '5, 8',
                opacity: 0.9
            }).addTo(map);
            
            lastMilePath.bindTooltip("<b>Safe Walk Handoff</b>", {
                permanent: true,
                direction: 'top',
                className: 'last-mile-tooltip'
            });
            routeLayers.push(lastMilePath);

            // Re-fit map if it's the first render or first route
            if (selectedRouteIndex === 0) {
                const routeBounds = L.latLngBounds(latlngs).extend(finalDestination);
                map.fitBounds(routeBounds, { padding: [60, 60], animate: true });
            }
        }
    }
}

function renderRouteList() {
    const container = document.getElementById('routes-container');
    container.innerHTML = '';
    
    currentRoutes.forEach((route, index) => {
        const isSelected = (index === selectedRouteIndex);
        container.innerHTML += createRouteCard(route, index, isSelected);
    });
}

// Window globally scoped function for onclick
window.selectRoute = function(index) {
    selectedRouteIndex = index;
    renderRoutes();
    renderRouteList();
}




// Basic polyline decoder

// Basic polyline decoder ported to JS
function decodePolyline(str, precision) {
    var index = 0,
        lat = 0,
        lng = 0,
        coordinates = [],
        shift = 0,
        result = 0,
        byte = null,
        latitude_change,
        longitude_change,
        factor = Math.pow(10, precision !== undefined ? precision : 5);

    while (index < str.length) {
        byte = null; shift = 0; result = 0;
        do {
            byte = str.charCodeAt(index++) - 63;
            result |= (byte & 0x1f) << shift;
            shift += 5;
        } while (byte >= 0x20);
        latitude_change = ((result & 1) ? ~(result >> 1) : (result >> 1));
        shift = result = 0;
        do {
            byte = str.charCodeAt(index++) - 63;
            result |= (byte & 0x1f) << shift;
            shift += 5;
        } while (byte >= 0x20);
        longitude_change = ((result & 1) ? ~(result >> 1) : (result >> 1));
        lat += latitude_change;
        lng += longitude_change;
        coordinates.push([lat / factor, lng / factor]);
    }
    return coordinates;
}

// Map Click to Set Start/End
map.on('click', function(e) {
    if (!startMarker) {
        startMarker = L.marker(e.latlng, { icon: startIcon }).addTo(map);
    } else if (!endMarker) {
        endMarker = L.marker(e.latlng, { icon: endIcon }).addTo(map);
        
        // Auto trigger routing
        const alpha = parseFloat(document.getElementById('alpha-slider').value);
        fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
        preFetchRoutes(startMarker.getLatLng(), endMarker.getLatLng());
    } else {
        // Reset
        map.removeLayer(startMarker);
        map.removeLayer(endMarker);
        startMarker = L.marker(e.latlng, { icon: startIcon }).addTo(map);
        endMarker = null;
        clearMap();
        document.getElementById('routes-container').innerHTML = '<div style="font-size: 13px; color: var(--text-muted); text-align: center; padding: 20px 0;">Select destination...</div>';
    }
});

// Event listener for Edge Toggle
const edgeToggle = document.getElementById('edge-toggle');
if (edgeToggle) {
    edgeToggle.addEventListener('change', () => {
        if (startMarker && endMarker) {
            const alpha = parseFloat(document.getElementById('alpha-slider').value);
            fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
        }
    });
}

// ── Geocoding helper (Nominatim) ──────────────────────────────────────────────
async function geocodePlace(query) {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1&countrycodes=in`;
    const res = await fetch(url, { headers: { 'Accept-Language': 'en' } });
    const data = await res.json();
    if (!data.length) throw new Error(`Place not found: "${query}"`);
    return L.latLng(parseFloat(data[0].lat), parseFloat(data[0].lon));
}

// Controls Map
document.getElementById('btn-clear').addEventListener('click', () => {
    if(startMarker) map.removeLayer(startMarker);
    if(endMarker) map.removeLayer(endMarker);
    startMarker = null;
    endMarker = null;
    clearMap();
    clearTowers();
    currentRoutes = [];
    document.getElementById('routes-container').innerHTML = '';
});

// Find Best Routes — geocode text inputs then route
document.getElementById('btn-find-routes').addEventListener('click', async () => {
    const originText = document.getElementById('input-origin').value.trim();
    const destText   = document.getElementById('input-dest').value.trim();
    
    console.log("Find Routes Clicked:", { originText, destText });

    if (!originText || !destText) {
        alert('Please enter both an Origin and a Destination address.');
        return;
    }
    const btn = document.getElementById('btn-find-routes');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;"></div> Searching...';

    try {
        const [s, e] = await Promise.all([geocodePlace(originText), geocodePlace(destText)]);
        if(startMarker) map.removeLayer(startMarker);
        if(endMarker)   map.removeLayer(endMarker);
        startMarker = L.marker(s, { icon: startIcon }).addTo(map);
        endMarker   = L.marker(e, { icon: endIcon }).addTo(map);
        drawRealTowers();
        map.fitBounds(L.latLngBounds(s, e), { padding: [50, 50] });
        const alpha = parseFloat(document.getElementById('alpha-slider').value);
        await fetchRoutes(s, e, alpha);
        preFetchRoutes(s, e);
    } catch (err) {
        alert(err.message || 'Geocoding failed. Try a more specific place name.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001q.044.06.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1 1 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0"/></svg> Find Best Routes';
    }
});

// Swap origin & destination text
document.getElementById('btn-swap').addEventListener('click', () => {
    const originEl = document.getElementById('input-origin');
    const destEl   = document.getElementById('input-dest');
    [originEl.value, destEl.value] = [destEl.value, originEl.value];
});

// Demo Route link — Marathahalli to Malleswaram
document.getElementById('btn-demo').addEventListener('click', () => {
    document.getElementById('input-origin').value = 'Marathahalli, Bangalore';
    document.getElementById('input-dest').value   = 'Malleswaram, Bangalore';
    if(startMarker) map.removeLayer(startMarker);
    if(endMarker)   map.removeLayer(endMarker);

    const s = L.latLng(12.9550, 77.7144);
    const e = L.latLng(12.9978, 77.5698);
    startMarker = L.marker(s, { icon: startIcon }).addTo(map);
    endMarker   = L.marker(e, { icon: endIcon }).addTo(map);
    drawRealTowers();
    map.fitBounds(L.latLngBounds(s, e), { padding: [50, 50] });
    const alpha = parseFloat(document.getElementById('alpha-slider').value);
    fetchRoutes(s, e, alpha);
    preFetchRoutes(s, e);
});

// Slice buttons
document.querySelectorAll('.slice-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        document.querySelectorAll('.slice-btn').forEach(b => b.classList.remove('active', 'btn-primary'));
        e.target.classList.add('active', 'btn-primary');
        if (startMarker && endMarker) {
            const alpha = parseFloat(document.getElementById('alpha-slider').value);
            fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
        }
    });
});

// Alpha Slider Real-time Interaction
const alphaSlider = document.getElementById('alpha-slider');
const alphaDisplay = document.getElementById('alpha-display');

if (alphaSlider) {
    alphaSlider.addEventListener('input', (e) => {
        const val = e.target.value;
        if (alphaDisplay) alphaDisplay.textContent = val;
        
        if (startMarker && endMarker) {
            // This will pull from cache if background pre-fetch finished
            fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), parseFloat(val));
        }
    });
}

// Weather toggle
const weatherToggle = document.getElementById('weather-toggle');
if (weatherToggle) {
    weatherToggle.addEventListener('change', () => {
        if (startMarker && endMarker) {
            const alpha = parseFloat(document.getElementById('alpha-slider').value);
            fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
        }
    });
}

// ISP Selector — re-fetch routes when ISP changes
const ispSelect = document.getElementById('isp-select');
if (ispSelect) {
    ispSelect.addEventListener('change', () => {
        routeCache.clear(); // ISP change invalidates cache
        if (startMarker && endMarker) {
            const alpha = parseFloat(document.getElementById('alpha-slider').value);
            fetchRoutes(startMarker.getLatLng(), endMarker.getLatLng(), alpha);
        }
        if (document.getElementById('heatmap-toggle') && document.getElementById('heatmap-toggle').checked) {
            fetchHeatmap();
        }
    });
}

// Heatmap feature
let heatmapLayers = [];

async function fetchHeatmap() {
    const isChecked = document.getElementById('heatmap-toggle').checked;
    
    heatmapLayers.forEach(l => map.removeLayer(l));
    heatmapLayers = [];

    if (!isChecked) return;

    document.getElementById('loader').classList.add('visible');
    try {
        const bounds = map.getBounds();
        const url = new URL('/heatmap', window.location.origin);
        url.searchParams.append('lat_min', bounds.getSouth());
        url.searchParams.append('lat_max', bounds.getNorth());
        url.searchParams.append('lon_min', bounds.getWest());
        url.searchParams.append('lon_max', bounds.getEast());
        url.searchParams.append('step', '0.02');

        const activeSliceBtn = document.querySelector('.slice-btn.active');
        url.searchParams.append('slice', activeSliceBtn ? activeSliceBtn.dataset.slice : 'default');

        const ispEl = document.getElementById('isp-select');
        if (ispEl && ispEl.value !== 'all') url.searchParams.append('isp', ispEl.value);

        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to load heatmap");
        
        const data = await response.json();
        
        data.cells.forEach(cell => {
            const bounds = [
                [cell.lat, cell.lon],
                [cell.lat + cell.step, cell.lon + cell.step]
            ];
            const rect = L.rectangle(bounds, {
                color: cell.color,
                weight: 0,
                fillColor: cell.color,
                fillOpacity: 0.25
            }).addTo(map);
            
            rect.bindTooltip(`<b>${cell.label}</b><br>Score: ${cell.score}<br>eCall: ${cell.ecall}`);
            
            rect.on('contextmenu', (e) => {
                // Right click to view explain
                buildExplainTooltip(cell.lat, cell.lon, data.slice_type);
            });
            
            heatmapLayers.push(rect);
        });
    } catch (e) {
        console.error("Heatmap error:", e);
    } finally {
        document.getElementById('loader').classList.remove('visible');
    }
}

const heatmapToggle = document.getElementById('heatmap-toggle');
if (heatmapToggle) {
    heatmapToggle.addEventListener('change', fetchHeatmap);
    map.on('moveend', () => {
        if (heatmapToggle.checked) fetchHeatmap();
    });
}

async function buildExplainTooltip(lat, lon, slice) {
    try {
        const ispEl = document.getElementById('isp-select');
        const ispParam = ispEl ? `&isp=${ispEl.value}` : '';
        const response = await fetch(`/api/explain?lat=${lat}&lon=${lon}&slice=${slice}${ispParam}`);
        const data = await response.json();
        
        let fb = data.feature_breakdown;
        let html = `
            <div style="font-family: Inter, sans-serif; min-width: 250px;">
                <h3 style="margin: 0 0 8px 0; font-size: 14px; text-transform: uppercase;">Connectivity Rationale</h3>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="font-size: 24px; font-weight: bold; color: ${data.score_color}">${data.score}</div>
                    <div style="font-size: 11px; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; color: ${data.score_color};">${data.ecall} eCall</div>
                </div>
                <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;"><strong>F1 Tower Density:</strong> ${fb.F1_tower_density}</div>
                <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;"><strong>F2 Signal Quality:</strong> ${fb.F2_signal_quality}</div>
                <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;"><strong>F5 Time of Day:</strong> ${fb.F5_time_of_day}</div>
                <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;"><strong>F7 Ookla Speed:</strong> ${fb.F7_ookla_throughput}</div>
                <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;"><strong>F11 5G Slice:</strong> ${fb.F11_5g_slice}</div>
                <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;"><strong>F15 Predictive:</strong> ${fb.F15_predictive}</div>
                <div style="font-size: 10px; color: #888; margin-top: 8px; font-style: italic;">${data.reason}</div>
            </div>
        `;
        L.popup()
            .setLatLng([lat, lon])
            .setContent(html)
            .openOn(map);
    } catch (e) {
        console.error(e);
    }
}

