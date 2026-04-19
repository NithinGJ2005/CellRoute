function showMessage(msg, duration = 3000) {
    const demoOverlay = document.getElementById('demo-overlay');
    const demoText = document.getElementById('demo-text');
    if (!demoOverlay || !demoText) return;

    demoText.innerHTML = msg;
    demoOverlay.style.display = 'block';
    return new Promise(resolve => setTimeout(resolve, duration));
}

async function runAutopilotDemo() {
    try {
        // Prevent multiple runs
        const btn = document.getElementById('pitch-mode-trigger');
        btn.disabled = true;
        btn.innerText = "DEMO IN PROGRESS...";

        // Step 1: Welcome
        await showMessage("Welcome to <b>CellRoute v2.5</b><br>The Future of Cellular-Aware Mobility.", 4000);
        
        // Step 2: Load Demo
        await showMessage("Step 1: Mapping the <b>Bangalore Digital Twin</b>...", 2500);
        const loadBtn = document.getElementById('btn-demo');
        if (loadBtn) loadBtn.click();
        
        await showMessage("Ingesting <b>4 real-world datasets</b> (OSM, Ookla, TRAI, OpenTraffic).<br>Analyzing path physics across 20M road segments.", 4500);

        // Step 3: Explain Slice
        await showMessage("Step 2: Provisioning <b>5G URLLC Slice</b> for safety-critical V2X...", 3000);
        const urllcBtn = document.querySelector('[data-slice="urllc"]');
        if (urllcBtn) urllcBtn.click();

        await showMessage("CellRoute ensures <b>eCall Compliance</b> (EU 2015/758).<br>Validating mission-critical signal thresholds in real-time.", 4500);

        // Step 4: Outage Simulation (The "Climax")
        await showMessage("Step 3: Simulating <b>Critical Infrastructure Failure</b>...", 2500);
        const outageBtn = document.getElementById('btn-outage');
        if (outageBtn) outageBtn.click();

        await showMessage("<b>NETWORK ALARM!</b><br>Tower KPI breach detected. Dead zone confirmed.", 3500);
        await showMessage("Dijkstra Engine is initiating <b>Closed-Loop Self-Healing</b>...<br>Automatically forcing a resilient detour.", 5000);

        // Step 5: Heatmap
        await showMessage("Step 4: visualising the <b>Global Coverage Map</b>...", 2500);
        const heatmapBtn = document.getElementById('heatmap-toggle');
        if (heatmapBtn && !heatmapBtn.checked) heatmapBtn.click();
        
        await showMessage("Total situational awareness restored.", 4000);

        // Step 6: Recovery
        await showMessage("Step 5: Executing <b>Network Recovery</b>...", 2500);
        const recoverBtn = document.getElementById('btn-recover');
        if (recoverBtn) recoverBtn.click();

        await showMessage("System stabilized. Infrastructure integrity 100%.", 4000);

        // Finish
        await showMessage("<b>Demo Complete.</b><br>CellRoute: Resilient. Intelligent. Submission Ready.", 5000);
        
        demoOverlay.style.display = 'none';
        btn.disabled = false;
        btn.innerText = "🚀 START GUIDED PITCH";

    } catch (err) {
        console.error("Demo failed:", err);
        demoOverlay.style.display = 'none';
        alert("Demo interrupted. Please check console.");
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const trigger = document.getElementById('pitch-mode-trigger');
    if (trigger) {
        trigger.addEventListener('click', runAutopilotDemo);
    }
});
