/**
 * CellRoute SignalBadge Component v2.1
 * Renders high-fidelity status badges with icons and tooltips.
 */

function renderSignalBadge(status) {
    let color = 'var(--text-muted)';
    let icon = '⚪';
    let text = 'Detecting...';

    if (status === 'excellent') {
        color = '#10b981';
        icon = '🟢';
        text = 'Excellent';
    } else if (status === 'good') {
        color = '#10b981';
        icon = '🟢';
        text = 'Good';
    } else if (status === 'moderate') {
        color = '#f59e0b';
        icon = '🟡';
        text = 'Moderate';
    } else if (status === 'poor') {
        color = '#f97316';
        icon = '🟠';
        text = 'Poor';
    } else if (status === 'dead zone') {
        color = '#ef4444';
        icon = '🔴';
        text = 'Dead Zone';
    }

    return `
        <div class="signal-badge" style="display: flex; align-items: center; gap: 5px; color: ${color}; font-size: 11px; font-weight: 600; background: ${color}15; padding: 2px 8px; border-radius: 4px; border: 1px solid ${color}30;">
            <span style="font-size: 8px;">${icon}</span>
            ${text.toUpperCase()}
        </div>
    `;
}

function renderECallBadge(status) {
    let color = '#94a3b8';
    let text = 'eCall: Unknown';
    let icon = '📞';

    if (status === 'reliable') {
        color = '#10b981';
        text = 'eCall: Certified';
        icon = '✓';
    } else if (status === 'marginal') {
        color = '#f59e0b';
        text = 'eCall: Marginal';
        icon = '⚠';
    } else {
        color = '#ef4444';
        text = 'eCall: Failure';
        icon = '✕';
    }

    return `
        <div class="ecall-badge" style="background: ${color}20; color: ${color}; border: 1px solid ${color}40; padding: 2px 6px; border-radius: 4px; font-size: 9px; font-weight: 800; display: inline-flex; align-items: center; gap: 4px; text-transform: uppercase; letter-spacing: 0.5px;">
            <span style="font-weight: 900;">${icon}</span> ${text}
        </div>
    `;
}
