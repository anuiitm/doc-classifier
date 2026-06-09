document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const queueList = document.getElementById('queue-list');
    const queueCount = document.getElementById('queue-count');
    const loadingOverlay = document.getElementById('loading-overlay');
    const toast = document.getElementById('toast');
    
    // Review Panel Elements
    const emptyPreview = document.getElementById('empty-preview');
    const reviewContent = document.getElementById('review-content');
    const previewFilename = document.getElementById('preview-filename');
    const previewLink = document.getElementById('preview-link');
    const viewerBody = document.getElementById('viewer-body');
    const detType = document.getElementById('det-type');
    const detId = document.getElementById('det-id');
    const detConfFill = document.getElementById('det-conf-fill');
    const detConfText = document.getElementById('det-conf-text');
    const detStatus = document.getElementById('det-status');
    const detNeedsReviewRow = document.getElementById('det-needs-review-row');
    
    // Actions
    const btnApprove = document.getElementById('btn-approve');
    const btnDecline = document.getElementById('btn-decline');
    const declineReasonBox = document.getElementById('decline-reason-box');
    const declineReasonText = document.getElementById('decline-reason');
    const btnCancelDecline = document.getElementById('btn-cancel-decline');
    const btnConfirmDecline = document.getElementById('btn-confirm-decline');

    let documentQueue = [];
    let currentDocIndex = -1;

    // --- Drag & Drop Handlers ---
    dropZone.addEventListener('click', () => fileInput.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    ['dragleave', 'dragend'].forEach(type => {
        dropZone.addEventListener(type, () => dropZone.classList.remove('dragover'));
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleUpload(e.dataTransfer.files);
        }
    });
    
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleUpload(fileInput.files);
            fileInput.value = ''; // reset
        }
    });

    // --- Upload Logic ---
    async function handleUpload(files) {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        
        showLoading(true);
        try {
            const res = await fetch('/classify-batch', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.error) throw new Error(data.error);
            
            // Add to queue
            data.forEach(item => {
                if(item.ok) {
                    documentQueue.push(item);
                } else {
                    showToast(`Failed to classify ${item.file}`, 'error');
                }
            });
            renderQueue();
            
            // Select first item if nothing is selected
            if (currentDocIndex === -1 && documentQueue.length > 0) {
                selectDocument(0);
            }
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            showLoading(false);
        }
    }

    // --- Queue Rendering ---
    function renderQueue() {
        queueCount.textContent = documentQueue.length;
        if (documentQueue.length === 0) {
            queueList.innerHTML = '<div class="empty-state">No documents in queue</div>';
            showReviewPanel(false);
            currentDocIndex = -1;
            return;
        }
        
        queueList.innerHTML = '';
        documentQueue.forEach((doc, idx) => {
            const el = document.createElement('div');
            el.className = `queue-item ${idx === currentDocIndex ? 'active' : ''}`;
            
            const conf = Math.round(doc.confidence * 100);
            const badgeClass = doc.decision === 'UNKNOWN' ? 'badge' : 'badge-primary';
            
            el.innerHTML = `
                <div class="queue-item-title" title="${doc.file}">${doc.file}</div>
                <div class="queue-item-meta">
                    <span class="${badgeClass}">${doc.display_name}</span>
                    <span>${conf}%</span>
                </div>
            `;
            el.onclick = () => selectDocument(idx);
            queueList.appendChild(el);
        });
    }

    // --- Selection Logic ---
    function selectDocument(idx) {
        if (idx < 0 || idx >= documentQueue.length) return;
        currentDocIndex = idx;
        renderQueue(); // update active state
        
        const doc = documentQueue[idx];
        showReviewPanel(true);
        
        previewFilename.textContent = doc.file;
        const url = `/uploads/${doc.server_filename}`;
        previewLink.href = url;
        
        // Render preview
        viewerBody.innerHTML = '';
        if (doc.server_filename.toLowerCase().endsWith('.pdf')) {
            viewerBody.innerHTML = `<embed src="${url}" type="application/pdf">`;
        } else {
            viewerBody.innerHTML = `<img src="${url}" alt="Preview">`;
        }
        
        // Details
        detType.textContent = doc.display_name;
        detId.textContent = doc.identifier || 'None';
        
        const conf = Math.round((doc.confidence || 0) * 100);
        detConfFill.style.width = `${conf}%`;
        detConfText.textContent = `${conf}%`;
        
        if (doc.needs_human_review || doc.decision === 'UNKNOWN') {
            detNeedsReviewRow.classList.remove('hidden');
        } else {
            detNeedsReviewRow.classList.add('hidden');
        }
        
        const extraFieldsContainer = document.getElementById('extra-fields-container');
        extraFieldsContainer.innerHTML = '';
        if (doc.extracted_fields && Object.keys(doc.extracted_fields).length > 0) {
            extraFieldsContainer.innerHTML = '<h4 style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; border-bottom: 1px solid var(--border-color); padding-bottom: 0.25rem; margin-bottom: 0.75rem;">Extracted Details</h4>';
            for (const [key, val] of Object.entries(doc.extracted_fields)) {
                extraFieldsContainer.innerHTML += `
                    <div class="detail-row" style="margin-bottom: 0.5rem;">
                        <span class="label" style="font-size: 0.7rem;">${key}</span>
                        <span class="value" style="font-size: 0.95rem;">${val}</span>
                    </div>
                `;
            }
        }
        
        // Reset action states
        declineReasonBox.classList.add('hidden');
        declineReasonText.value = '';
    }

    function showReviewPanel(show) {
        if (show) {
            emptyPreview.classList.add('hidden');
            reviewContent.classList.remove('hidden');
        } else {
            emptyPreview.classList.remove('hidden');
            reviewContent.classList.add('hidden');
        }
    }

    // --- Action Handlers ---
    btnApprove.addEventListener('click', () => {
        submitReview('APPROVED');
    });

    btnDecline.addEventListener('click', () => {
        declineReasonBox.classList.remove('hidden');
        declineReasonText.focus();
    });
    
    btnCancelDecline.addEventListener('click', () => {
        declineReasonBox.classList.add('hidden');
        declineReasonText.value = '';
    });
    
    btnConfirmDecline.addEventListener('click', () => {
        const reason = declineReasonText.value.trim();
        if (!reason) {
            showToast('Please provide a reason for declining.', 'error');
            return;
        }
        submitReview('DECLINED', reason);
    });

    async function submitReview(status, reason = '') {
        const doc = documentQueue[currentDocIndex];
        
        try {
            showLoading(true);
            const payload = {
                filename: doc.server_filename,
                doc_type: doc.decision === 'UNKNOWN' ? (doc.ranked[0]?.doc_type || 'UNKNOWN') : doc.decision,
                identifier: doc.identifier,
                status: status,
                reason: reason
            };
            
            const res = await fetch('/review', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (data.error) throw new Error(data.error);
            
            showToast(`Document ${status.toLowerCase()} successfully`, 'success');
            
            // Remove from queue
            documentQueue.splice(currentDocIndex, 1);
            currentDocIndex = documentQueue.length > 0 ? 0 : -1;
            renderQueue();
            if (currentDocIndex >= 0) {
                selectDocument(currentDocIndex);
            }
            
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            showLoading(false);
        }
    }

    // --- Utilities ---
    function showLoading(show) {
        if(show) loadingOverlay.classList.remove('hidden');
        else loadingOverlay.classList.add('hidden');
    }
    
    let toastTimeout;
    function showToast(msg, type = 'success') {
        toast.textContent = msg;
        toast.className = `toast ${type}`;
        toast.classList.remove('hidden');
        
        clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }
});
