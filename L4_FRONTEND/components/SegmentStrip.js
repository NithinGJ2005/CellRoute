// Generates the HTML for the colored segment bar based on connectivity scores
function createSegmentStrip(segmentScores) {
    if (!segmentScores || segmentScores.length === 0) return '';
    
    let segmentsHtml = '';
    
    segmentScores.forEach(score => {
        let color = 'var(--signal-good)';
        if (score < 0.3) {
            color = 'var(--signal-poor)';
        } else if (score < 0.6) {
            color = 'var(--signal-fair)';
        }
        
        segmentsHtml += `<div class="segment" style="background-color: ${color};"></div>`;
    });
    
    return `<div class="segment-strip-container">${segmentsHtml}</div>`;
}
