// Global variables to store application state
let inputVariables = [];
let outputVariables = [];
let selectedFile = null;
let variablesConfigured = false;

// Generic terms available for selection
const genericTerms = [
    { name: 'AMOUNT', description: 'Monetary amount or quantity' },
    { name: 'RATE', description: 'Percentage or ratio' },
    { name: 'TIME', description: 'Time period or duration' },
    { name: 'PRINCIPAL', description: 'Initial amount or base value' },
    { name: 'INTEREST', description: 'Interest amount or rate' },
    { name: 'DISCOUNT', description: 'Discount amount or percentage' },
    { name: 'TAX', description: 'Tax amount or rate' },
    { name: 'TOTAL', description: 'Sum or total amount' },
    { name: 'PRICE', description: 'Unit price or cost' },
    { name: 'QUANTITY', description: 'Number of items or units' }
];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeGenericTerms();
    setupDragAndDrop();
    updateButtonStates();
});

// Initialize generic terms display
function initializeGenericTerms() {
    const genericTermsList = document.getElementById('generic-terms-list');
    genericTermsList.innerHTML = '';
    
    genericTerms.forEach(term => {
        const termElement = document.createElement('div');
        termElement.className = 'generic-term-item';
        termElement.innerHTML = `
            <div>
                <strong>${term.name}</strong>
                <br>
                <small style="color: #6c757d;">${term.description}</small>
            </div>
            <button type="button" class="btn-add-generic" onclick="addGenericTerm('${term.name}', '${term.description}')">
                Add to Input
            </button>
        `;
        genericTermsList.appendChild(termElement);
    });
}

// Toggle generic terms visibility
function toggleGenericTerms() {
    const genericTerms = document.getElementById('generic-terms');
    const toggleText = document.getElementById('toggle-text');
    
    if (genericTerms.style.display === 'none') {
        genericTerms.style.display = 'block';
        toggleText.textContent = 'Hide Generic Variables';
    } else {
        genericTerms.style.display = 'none';
        toggleText.textContent = 'Show Generic Variables';
    }
}

// Add generic term to input variables
function addGenericTerm(name, description) {
    // Check if term already exists
    if (inputVariables.some(v => v.name === name)) {
        alert(`Variable "${name}" already exists in input variables!`);
        return;
    }
    
    inputVariables.push({ name, description });
    updateInputVariablesList();
    updateButtonStates();
}

// Add input variable
function addInputVariable() {
    const nameInput = document.getElementById('input-var-name');
    const descInput = document.getElementById('input-var-desc');
    
    const name = nameInput.value.trim().toUpperCase();
    const description = descInput.value.trim();
    
    if (!name) {
        alert('Please enter a variable name');
        return;
    }
    
    // Check if variable already exists
    if (inputVariables.some(v => v.name === name)) {
        alert(`Variable "${name}" already exists!`);
        return;
    }
    
    inputVariables.push({ name, description: description || 'No description provided' });
    updateInputVariablesList();
    
    // Clear inputs
    nameInput.value = '';
    descInput.value = '';
    
    updateButtonStates();
}

// Add output variable
function addOutputVariable() {
    const nameInput = document.getElementById('output-var-name');
    const name = nameInput.value.trim().toUpperCase();
    
    if (!name) {
        alert('Please enter an output variable name');
        return;
    }
    
    // Check if variable already exists
    if (outputVariables.some(v => v.name === name)) {
        alert(`Output variable "${name}" already exists!`);
        return;
    }
    
    outputVariables.push({ name });
    updateOutputVariablesList();
    
    // Clear input
    nameInput.value = '';
    
    updateButtonStates();
}

// Update input variables list display
function updateInputVariablesList() {
    const container = document.getElementById('input-variables');
    container.innerHTML = '';
    
    inputVariables.forEach((variable, index) => {
        const item = document.createElement('div');
        item.className = 'variable-item';
        item.innerHTML = `
            <div>
                <strong>${variable.name}</strong>
                <br>
                <small style="color: #6c757d;">${variable.description}</small>
            </div>
            <button type="button" class="btn-remove" onclick="removeInputVariable(${index})">
                Remove
            </button>
        `;
        container.appendChild(item);
    });
}

// Update output variables list display
function updateOutputVariablesList() {
    const container = document.getElementById('output-variables');
    container.innerHTML = '';
    
    outputVariables.forEach((variable, index) => {
        const item = document.createElement('div');
        item.className = 'variable-item';
        item.innerHTML = `
            <div>
                <strong>${variable.name}</strong>
            </div>
            <button type="button" class="btn-remove" onclick="removeOutputVariable(${index})">
                Remove
            </button>
        `;
        container.appendChild(item);
    });
}

// Remove input variable
function removeInputVariable(index) {
    inputVariables.splice(index, 1);
    updateInputVariablesList();
    updateButtonStates();
}

// Remove output variable
function removeOutputVariable(index) {
    outputVariables.splice(index, 1);
    updateOutputVariablesList();
    updateButtonStates();
}

// Save variables configuration
function saveVariables() {
    if (inputVariables.length === 0 && outputVariables.length === 0) {
        alert('Please add at least one input or output variable');
        return;
    }
    
    variablesConfigured = true;
    updateButtonStates();
    
    // Show success message
    const saveBtn = document.getElementById('save-variables-btn');
    const originalText = saveBtn.textContent;
    saveBtn.textContent = 'Variables Saved ✓';
    saveBtn.style.background = '#28a745';
    
    setTimeout(() => {
        saveBtn.textContent = originalText;
        saveBtn.style.background = '#4a90e2';
    }, 2000);
    
    console.log('Variables configuration saved:', {
        inputVariables,
        outputVariables
    });
}

// Setup drag and drop functionality
function setupDragAndDrop() {
    const dropzone = document.querySelector('.upload-dropzone');
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
    
    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
    });
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelection(files[0]);
        }
    });
}

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        handleFileSelection(file);
    }
}

// Process selected file
function handleFileSelection(file) {
    // Validate file type
    const allowedTypes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
    ];
    
    if (!allowedTypes.includes(file.type)) {
        alert('Please select a valid file type (PDF, DOC, DOCX, or TXT)');
        return;
    }
    
    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        alert('File size must be less than 10MB');
        return;
    }
    
    selectedFile = file;
    displayFileInfo(file);
    updateButtonStates();
}

// Display file information
function displayFileInfo(file) {
    const fileInfo = document.getElementById('file-info');
    const fileSize = (file.size / 1024 / 1024).toFixed(2);
    
    fileInfo.innerHTML = `
        <strong>Selected File:</strong> ${file.name}<br>
        <strong>Size:</strong> ${fileSize} MB<br>
        <strong>Type:</strong> ${file.type || 'Unknown'}
    `;
    fileInfo.style.display = 'block';
}

// Process document
function processDocument() {
    if (!variablesConfigured) {
        alert('Please configure and save variables first');
        return;
    }
    
    if (!selectedFile) {
        alert('Please select a file to process');
        return;
    }
    
    // Show loading state
    showLoading();
    
    // Simulate processing (replace with actual API call)
    setTimeout(() => {
        simulateFormulaExtraction();
    }, 2000);
}

// Show loading state
function showLoading() {
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = '<div class="loading">Processing document...</div>';
}

// Simulate formula extraction (replace with actual implementation)
function simulateFormulaExtraction() {
    const resultsContainer = document.getElementById('results-container');
    
    // Generate sample results based on configured variables
    const sampleResults = generateSampleResults();
    
    resultsContainer.innerHTML = '';
    
    if (sampleResults.length === 0) {
        resultsContainer.innerHTML = `
            <p style="text-align: center; color: #6c757d; padding: 40px;">
                No formulas found matching your configured variables.
            </p>
        `;
        return;
    }
    
    sampleResults.forEach(result => {
        const resultElement = document.createElement('div');
        resultElement.className = 'formula-result';
        resultElement.innerHTML = `
            <h4>Formula Found</h4>
            <p><strong>Formula:</strong> ${result.formula}</p>
            <p><strong>Context:</strong> ${result.context}</p>
            <p><strong>Variables Used:</strong> ${result.variables.join(', ')}</p>
            <p><strong>Confidence:</strong> ${result.confidence}%</p>
        `;
        resultsContainer.appendChild(resultElement);
    });
}

// Generate sample results based on configured variables
function generateSampleResults() {
    const results = [];
    
    // Sample formulas based on common input variables
    const formulaTemplates = [
        {
            formula: 'TOTAL = PRINCIPAL + INTEREST',
            context: 'Simple interest calculation',
            requiredVars: ['PRINCIPAL', 'INTEREST', 'TOTAL']
        },
        {
            formula: 'DISCOUNT_AMOUNT = PRICE × DISCOUNT_RATE',
            context: 'Discount calculation',
            requiredVars: ['PRICE', 'DISCOUNT', 'AMOUNT']
        },
        {
            formula: 'TOTAL_COST = QUANTITY × PRICE + TAX',
            context: 'Total cost calculation with tax',
            requiredVars: ['QUANTITY', 'PRICE', 'TAX', 'TOTAL']
        },
        {
            formula: 'INTEREST = PRINCIPAL × RATE × TIME',
            context: 'Simple interest formula',
            requiredVars: ['PRINCIPAL', 'RATE', 'TIME', 'INTEREST']
        }
    ];
    
    const allVariables = [...inputVariables.map(v => v.name), ...outputVariables.map(v => v.name)];
    
    formulaTemplates.forEach(template => {
        const matchingVars = template.requiredVars.filter(reqVar => 
            allVariables.some(userVar => 
                userVar.includes(reqVar) || reqVar.includes(userVar)
            )
        );
        
        if (matchingVars.length >= 2) {
            results.push({
                formula: template.formula,
                context: template.context,
                variables: matchingVars,
                confidence: Math.floor(Math.random() * 20) + 80 // 80-100%
            });
        }
    });
    
    return results;
}

// Update button states based on current application state
function updateButtonStates() {
    const saveVarsBtn = document.getElementById('save-variables-btn');
    const processBtn = document.getElementById('process-btn');
    
    // Enable save variables button if there are variables to save
    saveVarsBtn.disabled = inputVariables.length === 0 && outputVariables.length === 0;
    
    // Enable process button if variables are configured and file is selected
    processBtn.disabled = !variablesConfigured || !selectedFile;
}

// Handle enter key press in input fields
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        const target = e.target;
        
        if (target.id === 'input-var-name' || target.id === 'input-var-desc') {
            addInputVariable();
        } else if (target.id === 'output-var-name') {
            addOutputVariable();
        }
    }
});