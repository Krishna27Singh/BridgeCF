// Ensure we don't accidentally run multiple injection routines
if (!window.hintEngineInjected) {
    window.hintEngineInjected = true;
    
    // Inject the component when the page finishes loading
    window.addEventListener("load", () => {
        injectHintUI();
    });
}

function injectHintUI() {
    // Locate the standard right-hand sidebar box element on Codeforces
    const sidebar = document.querySelector("#sidebar");
    if (!sidebar) return;

    // Create a container div
    const container = document.createElement("div");
    container.style.border = "1px solid #b9b9b9";
    container.style.borderRadius = "4px";
    container.style.padding = "10px";
    container.style.marginBottom = "15px";
    container.style.backgroundColor = "#fff";

    // Add title
    const title = document.createElement("h4");
    title.innerText = "Pedagogical Hint Engine";
    title.style.margin = "0 0 10px 0";
    container.appendChild(title);

    // Add action button
    const button = document.createElement("button");
    button.innerText = "Get Adaptive Hint";
    button.style.width = "100%";
    button.style.padding = "8px";
    button.style.cursor = "pointer";
    container.appendChild(button);

    // Add a text area for displaying responses
    const displayArea = document.createElement("div");
    displayArea.style.marginTop = "10px";
    displayArea.style.fontSize = "12px";
    container.appendChild(displayArea);

    // Insert our custom box at the top of the sidebar
    sidebar.insertBefore(container, sidebar.firstChild);

    // Setup action listener
    button.addEventListener("click", async () => {
        displayArea.innerText = "Querying backend engine...";
        
        // Extract basic parameters from current URL structure
        const currentUrl = window.location.pathname; 
        const problemId = currentUrl.split("/").filter(Boolean).slice(-2).join("_");

        // Temporary hardcoded handle until we plug in full profile extraction
        const userHandle = "guest_user"; 

        try {
            const response = await fetch("http://127.0.0.1:8000/api/hint", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ problem_id: problemId, user_handle: userHandle })
            });
            
            const data = await response.json();
            if (data.status === "success") {
                displayArea.innerHTML = `
                    <p><strong>Step-by-Step Guidance:</strong></p>
                    <ul>
                        <li>${data.hints[1]}</li>
                        <li>${data.hints[2]}</li>
                    </ul>
                    <p><a href="${data.bridge_problem}" target="_blank">Try Bridge Problem</a></p>
                `;
            } else {
                displayArea.innerText = "Failed to load hints properly.";
            }
        } catch (error) {
            displayArea.innerText = "Error: Cannot connect to the local FastAPI server.";
            console.error(error);
        }
    });
}