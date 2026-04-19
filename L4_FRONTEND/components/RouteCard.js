// Generates the HTML for a single route card
function createRouteCard(route, index, isSelected) {
    const durationMin = Math.round(route.duration / 60);
    const distanceKm = (route.distance / 1000).toFixed(1);
    
    // connectivity_score is already 0-100 from the backend
    const signalScore = route.connectivity_score || 0;
    const compScore = Math.round(route.route_score || route.connectivity_score || 0);
    
    let deadZoneBadge = '';
    if (route.deadzone_count > 0) {
        deadZoneBadge = `<span class="badge-danger">${route.deadzone_count} Dead zones</span>`;
    }

    let enrichHtml = '';
    if (route.hasOwnProperty('f9_handoff_bonus')) {
        const ecallBadge = renderECallBadge(
            route.ecall_reliable_fraction > 0.9 ? 'reliable' : (route.ecall_reliable_fraction > 0.5 ? 'marginal' : 'failure')
        );
        
        let sliceStr = '';
        if (route.slice_type === 'urllc') sliceStr = 'URLLC (V2X)';
        else if (route.slice_type === 'embb') sliceStr = 'eMBB (HD)';

        enrichHtml = `
            <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center;">
                ${ecallBadge}
                <span style="font-size: 10px; font-weight: 700; color: #94a3b8; display: flex; align-items: center; gap: 3px;">
                    <span style="font-size: 14px;">📡</span> ${route.handoff_count} HANDOFFS
                </span>
                ${sliceStr ? `<span style="font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; background: rgba(59, 130, 246, 0.2); color: #93c5fd; text-transform: uppercase;">${sliceStr}</span>` : ''}
            </div>
        `;
    }

    const segmentStrip = createSegmentStrip(route.segment_scores);
    
    return `
        <div class="route-card ${isSelected ? 'selected' : ''}" data-index="${index}" onclick="selectRoute(${index})" style="padding: 12px;">
            <div class="route-header" style="margin-bottom: 6px;">
                <div class="route-title" style="font-family: 'Outfit', sans-serif; font-size: 13px;">${route.route_label || route.primary_road || 'Trajectory'}</div>
                <div class="route-score" style="font-size: 16px; color: ${isSelected ? 'var(--accent-brand)' : 'var(--text-main)'}">
                    ${compScore}<span style="font-size: 9px; font-weight: normal; color: var(--text-muted)">/100</span>
                </div>
            </div>
            
            <div class="route-stats" style="margin-bottom: ${enrichHtml ? '8px' : '10px'}; font-size: 11px; gap: 10px;">
                <div class="stat"><span style="color: #60a5fa;">${durationMin}</span>m</div>
                <div class="stat"><span style="color: #60a5fa;">${distanceKm}</span>km</div>
                <div class="stat" style="color: var(--signal-good)"><span>${signalScore}%</span></div>
                ${deadZoneBadge}
            </div>
            
            ${enrichHtml}
            ${segmentStrip}
        </div>
    `;
}

