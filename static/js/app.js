// Application State
const state = {
    config: null,
    currentPath: '',
    photos: [],
    markedPhotos: new Set(),
    currentView: 'grid',
    currentCarouselIndex: 0,
    loadedPhotos: 50,
    isReviewFolder: false
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadConfig();
    setupEventListeners();
    loadVersion();
});

// Tab Management
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active'));

            tab.classList.add('active');
            const targetTab = tab.dataset.tab;

            if (targetTab === 'config') {
                document.getElementById('config-tab').classList.add('active');
            } else if (targetTab === 'reviewer') {
                document.getElementById('reviewer-tab-content').classList.add('active');
            } else if (targetTab === 'help') {
                document.getElementById('help-tab').classList.add('active');
            }
        });
    });
}

// Event Listeners
function setupEventListeners() {
    // Config events
    document.getElementById('add-mount-point').addEventListener('click', addMountPoint);
    document.getElementById('save-config').addEventListener('click', saveConfig);

    // Panel dual navigation events
    document.getElementById('back-btn').addEventListener('click', navigateBack);
    document.getElementById('toggle-folders').addEventListener('click', toggleFoldersPanel);

    // Reviewer events
    document.getElementById('toggle-view').addEventListener('click', toggleView);
    document.getElementById('unmark-all').addEventListener('click', unmarkAll);
    document.getElementById('delete-jpgs').addEventListener('click', showDeleteJpgsModal);
    document.getElementById('move-photos').addEventListener('click', movePhotos);
    document.getElementById('restore-photos').addEventListener('click', restorePhotos);
    document.getElementById('delete-photos').addEventListener('click', showDeleteModal);
    document.getElementById('carousel-prev').addEventListener('click', () => navigateCarousel(-1));
    document.getElementById('carousel-next').addEventListener('click', () => navigateCarousel(1));
    document.getElementById('carousel-close').addEventListener('click', closeCarousel);

    // Delete modal events
    document.getElementById('delete-cancel').addEventListener('click', hideDeleteModal);
    document.getElementById('delete-confirm').addEventListener('click', deletePhotos);
    document.getElementById('delete-confirmation-input').addEventListener('input', (e) => {
        const btn = document.getElementById('delete-confirm');
        btn.disabled = e.target.value !== 'ELIMINAR';
    });

    // Delete JPGs modal events
    document.getElementById('delete-jpgs-cancel').addEventListener('click', hideDeleteJpgsModal);
    document.getElementById('delete-jpgs-confirm').addEventListener('click', deleteJpgs);

    // Keyboard shortcuts for carousel
    document.addEventListener('keydown', handleKeyboard);

    // Lazy loading
    const photosGrid = document.getElementById('photos-grid');
    if (photosGrid) {
        photosGrid.addEventListener('scroll', handleScroll);
    }
}

// Config Functions
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        state.config = config;

        // Ensure enable_delete_button exists
        if (state.config.enable_delete_button === undefined) {
            state.config.enable_delete_button = false;
        }

        renderConfig();
        checkPermissions();
        initNavigation();
    } catch (error) {
        showToast('Error cargando configuración', 'error');
        console.error(error);
    }
}

function renderConfig() {
    const mountPointsList = document.getElementById('mount-points-list');
    mountPointsList.innerHTML = '';

    state.config.mount_points.forEach((mp, index) => {
        const div = document.createElement('div');
        div.className = 'mount-point-item';
        div.innerHTML = `
            <span>${mp}</span>
            <button class="btn-danger" onclick="removeMountPoint(${index})">Eliminar</button>
        `;
        mountPointsList.appendChild(div);
    });

    document.getElementById('destination-folder').value = state.config.destination_folder;
    document.getElementById('enable-delete-button').checked = state.config.enable_delete_button || false;
}

function addMountPoint() {
    const input = document.getElementById('new-mount-point');
    const path = input.value.trim();

    if (!path) {
        showToast('Ingresa una ruta válida', 'error');
        return;
    }

    if (state.config.mount_points.includes(path)) {
        showToast('Este punto de montaje ya existe', 'error');
        return;
    }

    state.config.mount_points.push(path);
    input.value = '';
    renderConfig();
}

function removeMountPoint(index) {
    state.config.mount_points.splice(index, 1);
    renderConfig();
}

async function saveConfig() {
    const destinationFolder = document.getElementById('destination-folder').value.trim();
    const enableDeleteButton = document.getElementById('enable-delete-button').checked;

    if (!destinationFolder) {
        showToast('Ingresa un nombre de carpeta de destino', 'error');
        return;
    }

    state.config.destination_folder = destinationFolder;
    state.config.enable_delete_button = enableDeleteButton;

    try {
        showLoading(true);
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.config)
        });

        const result = await response.json();

        if (result.success) {
            showToast('Configuración guardada', 'success');
            checkPermissions();
            loadBrowser();
        } else {
            showToast('Error guardando configuración', 'error');
        }
    } catch (error) {
        showToast('Error guardando configuración', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

async function checkPermissions() {
    const diagnostic = document.getElementById('permissions-diagnostic');
    diagnostic.innerHTML = '<p>Verificando permisos...</p>';

    const results = [];

    for (const mp of state.config.mount_points) {
        try {
            const response = await fetch(`/api/check-permissions?path=${encodeURIComponent(mp)}`);
            const data = await response.json();
            results.push({ path: mp, ...data });
        } catch (error) {
            results.push({ path: mp, exists: false, readable: false, writable: false });
        }
    }

    diagnostic.innerHTML = '';

    results.forEach(result => {
        const div = document.createElement('div');
        div.className = 'permission-item';

        if (result.exists && result.readable && result.writable) {
            div.classList.add('success');
            div.innerHTML = `
                <h3>✓ ${result.path}</h3>
                <p>Accesible y con permisos correctos</p>
            `;
        } else {
            div.classList.add('error');
            let issues = [];
            if (!result.exists) issues.push('No existe');
            if (!result.readable) issues.push('Sin permisos de lectura');
            if (!result.writable) issues.push('Sin permisos de escritura');

            div.innerHTML = `
                <h3>✗ ${result.path}</h3>
                <p>Problemas: ${issues.join(', ')}</p>
                <code>sudo chown -R santosg:santosg ${result.path}
sudo chmod -R 755 ${result.path}
# Si es montaje Samba:
sudo mount -o remount,uid=santosg,gid=santosg ${result.path}</code>
            `;
        }

        diagnostic.appendChild(div);
    });
}

// Panel Dual Navigation Functions
async function navigateToFolder(path) {
    state.currentPath = path;

    // Ocultar carrusel si está activo
    document.getElementById('carousel-view').classList.remove('active');
    document.getElementById('revisor-panel').style.display = 'flex';

    updateBreadcrumb(path);

    try {
        showLoading(true);

        // Cargar subcarpetas y fotos simultáneamente
        const [foldersData, photosData] = await Promise.all([
            loadSubfolders(path),
            loadPhotos(path)
        ]);

        // Renderizar carpetas
        renderFolders(foldersData);

        // Renderizar fotos
        renderPhotos(photosData);

        // Actualizar contadores
        document.getElementById('folder-count').textContent = foldersData.length;
        document.getElementById('photo-count').textContent = photosData.length;

        // Si no hay subcarpetas, ocultar panel automáticamente
        const foldersPanel = document.getElementById('folders-panel');
        if (foldersData.length === 0) {
            foldersPanel.classList.add('collapsed');
            document.getElementById('toggle-folders').textContent = '▶ Expandir';
        } else {
            foldersPanel.classList.remove('collapsed');
            document.getElementById('toggle-folders').textContent = '▼ Colapsar';
        }

    } catch (error) {
        showToast('Error cargando carpeta', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

async function loadSubfolders(path) {
    try {
        const url = path ? `/api/browse?path=${encodeURIComponent(path)}` : '/api/browse';
        const response = await fetch(url);
        const data = await response.json();

        if (data.error) {
            return [];
        }

        return data.items || [];
    } catch (error) {
        console.error('Error loading subfolders:', error);
        return [];
    }
}

async function loadPhotos(path) {
    if (!path) {
        return [];
    }

    try {
        const response = await fetch(`/api/scan?path=${encodeURIComponent(path)}`);
        const data = await response.json();

        if (data.error || !data.photos) {
            return [];
        }

        state.photos = data.photos;
        state.markedPhotos.clear();
        state.loadedPhotos = 50;

        // Check if this is a review folder
        checkIfReviewFolder();

        return data.photos;
    } catch (error) {
        console.error('Error loading photos:', error);
        return [];
    }
}

// Breadcrumb Navigation
function updateBreadcrumb(path) {
    const breadcrumbPath = document.getElementById('breadcrumb-path');
    breadcrumbPath.innerHTML = '';

    // Botón Atrás habilitado/deshabilitado
    const backBtn = document.getElementById('back-btn');
    backBtn.disabled = !path;

    if (!path) {
        const rootItem = document.createElement('span');
        rootItem.className = 'breadcrumb-item current';
        rootItem.textContent = 'Raíz';
        breadcrumbPath.appendChild(rootItem);
        return;
    }

    const parts = path.split('/').filter(p => p);
    let currentPath = '';

    // Botón Raíz
    const rootItem = document.createElement('span');
    rootItem.className = 'breadcrumb-item';
    rootItem.textContent = 'Raíz';
    rootItem.addEventListener('click', () => navigateToFolder(''));
    breadcrumbPath.appendChild(rootItem);

    parts.forEach((part, index) => {
        // Separador
        const separator = document.createElement('span');
        separator.className = 'breadcrumb-separator';
        separator.textContent = ' / ';
        breadcrumbPath.appendChild(separator);

        currentPath += '/' + part;
        const pathCopy = currentPath;

        const item = document.createElement('span');
        item.className = 'breadcrumb-item';
        item.textContent = part;

        if (index < parts.length - 1) {
            item.addEventListener('click', () => navigateToFolder(pathCopy));
        } else {
            item.classList.add('current');
        }

        breadcrumbPath.appendChild(item);
    });
}

// Navigate Back
function navigateBack() {
    if (!state.currentPath) return;

    const pathParts = state.currentPath.split('/').filter(p => p);
    pathParts.pop(); // Quitar último
    const parentPath = pathParts.length > 0 ? '/' + pathParts.join('/') : '';
    navigateToFolder(parentPath);
}

// Toggle Folders Panel
function toggleFoldersPanel() {
    const panel = document.getElementById('folders-panel');
    panel.classList.toggle('collapsed');

    const btn = document.getElementById('toggle-folders');
    btn.textContent = panel.classList.contains('collapsed')
        ? '▶ Expandir'
        : '▼ Colapsar';
}

// Render Folders
function renderFolders(folders) {
    const foldersGrid = document.getElementById('folders-grid');
    foldersGrid.innerHTML = '';

    if (folders.length === 0) {
        foldersGrid.innerHTML = '<p style="grid-column: 1 / -1; text-align: center; color: #666; padding: 20px;">No hay subcarpetas</p>';
        return;
    }

    folders.forEach(folder => {
        const div = document.createElement('div');
        div.className = 'folder-item';
        div.textContent = folder.name;
        div.addEventListener('click', () => navigateToFolder(folder.path));
        foldersGrid.appendChild(div);
    });
}

// Render Photos
function renderPhotos(photos) {
    const photosGrid = document.getElementById('photos-grid');
    photosGrid.innerHTML = '';

    if (photos.length === 0) {
        photosGrid.innerHTML = '<p style="grid-column: 1 / -1; text-align: center; color: #666; padding: 40px;">No hay fotos en esta carpeta</p>';
        updateActionButtons();
        return;
    }

    const photosToLoad = photos.slice(0, state.loadedPhotos);

    photosToLoad.forEach((photo, index) => {
        const div = document.createElement('div');
        div.className = 'photo-item';
        if (state.markedPhotos.has(index)) {
            div.classList.add('marked');
        }

        // Add tooltip
        const sizeKB = Math.round(photo.size / 1024);
        const rawStatus = photo.raw ? 'con RAW' : 'sin RAW';
        div.title = `${photo.name}\n${sizeKB} KB - ${rawStatus}`;

        const img = document.createElement('img');
        img.src = `/api/thumbnail?path=${encodeURIComponent(photo.display_path)}`;
        img.loading = 'lazy';
        img.alt = photo.name;

        // Add loaded class when image loads
        img.addEventListener('load', () => {
            img.classList.add('loaded');
        });

        const checkbox = document.createElement('div');
        checkbox.className = 'photo-checkbox';
        if (state.markedPhotos.has(index)) {
            checkbox.classList.add('checked');
        }

        checkbox.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleMark(index);
        });

        // Create badges
        const badges = createBadges(photo);

        // Add play icon for videos
        if (photo.type === 'video') {
            const playIcon = document.createElement('div');
            playIcon.className = 'video-play-icon';
            div.appendChild(playIcon);
        }

        // Add file name label
        const fileName = document.createElement('div');
        fileName.className = 'file-name';
        const nameWithoutExt = photo.name.replace(/\.[^/.]+$/, '');
        fileName.textContent = nameWithoutExt.length > 20
            ? nameWithoutExt.substring(0, 20) + '...'
            : nameWithoutExt;
        fileName.title = nameWithoutExt; // Full name on hover

        div.addEventListener('click', () => {
            showCarousel(index);
        });

        div.appendChild(img);
        div.appendChild(badges);
        div.appendChild(checkbox);
        div.appendChild(fileName);
        photosGrid.appendChild(div);
    });

    if (state.loadedPhotos < state.photos.length) {
        const loadMore = document.createElement('div');
        loadMore.style.gridColumn = '1 / -1';
        loadMore.style.textAlign = 'center';
        loadMore.style.padding = '20px';
        loadMore.style.color = '#666';
        loadMore.textContent = `Mostrando ${state.loadedPhotos} de ${state.photos.length} fotos`;
        photosGrid.appendChild(loadMore);
    }

    updateCounters();
    updateActionButtons();
}

function checkIfReviewFolder() {
    const folderName = state.currentPath.split('/').filter(p => p).pop();
    state.isReviewFolder = folderName === state.config.destination_folder;
}

function updateActionButtons() {
    const moveBtn = document.getElementById('move-photos');
    const restoreBtn = document.getElementById('restore-photos');
    const deleteBtn = document.getElementById('delete-photos');
    const deleteJpgsBtn = document.getElementById('delete-jpgs');

    if (state.isReviewFolder) {
        // In review folder
        moveBtn.style.display = 'none';
        deleteJpgsBtn.style.display = 'none';
        restoreBtn.style.display = 'inline-block';

        if (state.config.enable_delete_button) {
            deleteBtn.style.display = 'inline-block';
        } else {
            deleteBtn.style.display = 'none';
        }
    } else {
        // In normal folder
        moveBtn.style.display = 'inline-block';
        deleteJpgsBtn.style.display = 'inline-block';
        restoreBtn.style.display = 'none';
        deleteBtn.style.display = 'none';
    }
}

// Inicializar navegación (llamado desde loadConfig)
async function initNavigation() {
    await navigateToFolder('');
}

function createBadges(photo) {
    const badgesDiv = document.createElement('div');
    badgesDiv.className = 'photo-badges';

    // Video badge
    if (photo.type === 'video') {
        const videoBadge = document.createElement('div');
        videoBadge.className = 'badge badge-video';
        videoBadge.textContent = 'VIDEO';
        badgesDiv.appendChild(videoBadge);
        return badgesDiv;
    }

    // Format badge for images
    const formatBadge = document.createElement('div');
    formatBadge.className = 'badge badge-format';

    if (photo.type === 'jpg+raw') {
        formatBadge.classList.add('jpg-raw');
        formatBadge.textContent = 'JPG+RAW';
    } else if (photo.type === 'jpg_only') {
        formatBadge.classList.add('jpg-only');
        formatBadge.textContent = 'Solo JPG';
    } else if (photo.type === 'raw_only') {
        formatBadge.classList.add('raw-only');
        formatBadge.textContent = 'Solo RAW';
    }

    badgesDiv.appendChild(formatBadge);

    // Camera badge
    if (photo.camera_brand) {
        const cameraBadge = document.createElement('div');
        cameraBadge.className = 'badge badge-camera';
        cameraBadge.textContent = photo.camera_brand;
        badgesDiv.appendChild(cameraBadge);
    }

    return badgesDiv;
}

// Carousel View
function showCarousel(index) {
    state.currentCarouselIndex = index;
    state.currentView = 'carousel';

    // Ocultar panel dual y mostrar carrusel
    document.getElementById('revisor-panel').style.display = 'none';
    document.getElementById('carousel-view').classList.add('active');

    updateCarousel();
    preloadNextImage();
}

function updateCarousel() {
    const photo = state.photos[state.currentCarouselIndex];
    const img = document.getElementById('carousel-image');
    const video = document.getElementById('carousel-video');
    const loadingOverlay = document.getElementById('carousel-loading-overlay');

    // Show loading overlay
    loadingOverlay.style.display = 'flex';

    // Check if it's a video
    if (photo.type === 'video') {
        // Hide image, show video
        img.style.display = 'none';
        video.style.display = 'block';

        // Set video source
        video.src = `/api/video?path=${encodeURIComponent(photo.display_path)}`;

        // Add marked class if needed
        if (state.markedPhotos.has(state.currentCarouselIndex)) {
            video.classList.add('marked');
        } else {
            video.classList.remove('marked');
        }

        // Hide loading when video can play
        video.addEventListener('loadeddata', () => {
            loadingOverlay.style.display = 'none';
        }, { once: true });

        video.addEventListener('error', () => {
            loadingOverlay.style.display = 'none';
            showToast('Error cargando video', 'error');
        }, { once: true });

    } else {
        // It's an image
        // Hide video, show image
        video.style.display = 'none';
        img.style.display = 'block';

        // Pause video if it was playing
        video.pause();
        video.src = '';

        // Create a new image to preload
        const newImg = new Image();

        newImg.onload = () => {
            // Hide loading overlay when image is loaded
            loadingOverlay.style.display = 'none';
            img.src = newImg.src;

            if (state.markedPhotos.has(state.currentCarouselIndex)) {
                img.classList.add('marked');
            } else {
                img.classList.remove('marked');
            }
        };

        newImg.onerror = () => {
            // Hide loading overlay on error too
            loadingOverlay.style.display = 'none';
            showToast('Error cargando imagen', 'error');
        };

        // Start loading the image
        newImg.src = `/api/image?path=${encodeURIComponent(photo.display_path)}`;
    }

    // Update carousel badges
    const badgesContainer = document.getElementById('carousel-badges');
    badgesContainer.innerHTML = '';
    const badges = createBadges(photo);
    badgesContainer.appendChild(badges);

    updateCounters();
}

function preloadNextImage() {
    // Preload next image for smoother navigation
    const nextIndex = (state.currentCarouselIndex + 1) % state.photos.length;
    const nextPhoto = state.photos[nextIndex];

    const preloadImg = new Image();
    preloadImg.src = `/api/image?path=${encodeURIComponent(nextPhoto.display_path)}`;
}

function navigateCarousel(direction) {
    state.currentCarouselIndex += direction;

    if (state.currentCarouselIndex < 0) {
        state.currentCarouselIndex = state.photos.length - 1;
    } else if (state.currentCarouselIndex >= state.photos.length) {
        state.currentCarouselIndex = 0;
    }

    updateCarousel();
    preloadNextImage();
}

// Marking Functions
function toggleMark(index) {
    if (state.markedPhotos.has(index)) {
        state.markedPhotos.delete(index);
    } else {
        state.markedPhotos.add(index);
    }

    if (state.currentView === 'grid') {
        renderPhotos(state.photos);
    } else {
        updateCarousel();
    }

    updateCounters();
}

function unmarkAll() {
    if (state.markedPhotos.size === 0) return;

    if (confirm('¿Desmarcar todas las fotos?')) {
        state.markedPhotos.clear();

        if (state.currentView === 'grid') {
            renderPhotos(state.photos);
        } else {
            updateCarousel();
        }

        updateCounters();
    }
}

// Move Photos
async function movePhotos() {
    const count = state.markedPhotos.size;

    if (count === 0) {
        showToast('No hay fotos marcadas', 'error');
        return;
    }

    if (!confirm(`¿Mover ${count} fotos a la carpeta "${state.config.destination_folder}"?`)) {
        return;
    }

    try {
        showLoading(true);

        const filesToMove = Array.from(state.markedPhotos).map(index => state.photos[index]);

        const response = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder: state.currentPath,
                files: filesToMove,
                destination_name: state.config.destination_folder
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`${result.moved} fotos movidas correctamente`, 'success');
            // Reload current folder
            await navigateToFolder(state.currentPath);
        } else {
            showToast(result.error || 'Error moviendo fotos', 'error');
        }
    } catch (error) {
        showToast('Error moviendo fotos', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

// Restore Photos
async function restorePhotos() {
    const count = state.markedPhotos.size;

    if (count === 0) {
        showToast('No hay fotos marcadas', 'error');
        return;
    }

    if (!confirm(`¿Restaurar ${count} fotos a la carpeta padre?`)) {
        return;
    }

    try {
        showLoading(true);

        const filesToRestore = Array.from(state.markedPhotos).map(index => state.photos[index]);

        const response = await fetch('/api/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder: state.currentPath,
                files: filesToRestore
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`${result.restored} fotos restauradas correctamente`, 'success');
            // Reload current folder
            await navigateToFolder(state.currentPath);
        } else {
            showToast(result.error || 'Error restaurando fotos', 'error');
        }
    } catch (error) {
        showToast('Error restaurando fotos', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

// Delete Photos
function showDeleteModal() {
    const count = state.markedPhotos.size;

    if (count === 0) {
        showToast('No hay fotos marcadas', 'error');
        return;
    }

    const modal = document.getElementById('delete-modal');
    const message = document.getElementById('delete-modal-message');
    const input = document.getElementById('delete-confirmation-input');

    message.textContent = `¿Eliminar definitivamente ${count} archivos? Esta acción no se puede deshacer.`;
    input.value = '';
    document.getElementById('delete-confirm').disabled = true;

    modal.style.display = 'flex';
}

function hideDeleteModal() {
    document.getElementById('delete-modal').style.display = 'none';
}

async function deletePhotos() {
    try {
        showLoading(true);
        hideDeleteModal();

        const filesToDelete = Array.from(state.markedPhotos).map(index => state.photos[index]);

        const response = await fetch('/api/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: filesToDelete
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`${result.deleted} fotos eliminadas correctamente`, 'success');
            // Reload current folder
            await navigateToFolder(state.currentPath);
        } else {
            showToast(result.error || 'Error eliminando fotos', 'error');
        }
    } catch (error) {
        showToast('Error eliminando fotos', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

// Delete JPGs Modal
function showDeleteJpgsModal() {
    const markedCount = state.markedPhotos.size;

    if (markedCount === 0) {
        showToast('No hay fotos marcadas', 'error');
        return;
    }

    // Count how many marked photos have both JPG+RAW
    const markedPhotos = Array.from(state.markedPhotos).map(index => state.photos[index]);
    const jpgRawPhotos = markedPhotos.filter(photo => photo.type === 'jpg+raw');
    const jpgOnlyPhotos = markedPhotos.filter(photo => photo.type === 'jpg_only');

    if (jpgRawPhotos.length === 0) {
        showToast('No hay fotos JPG+RAW marcadas. Solo se eliminan JPGs que tienen RAW.', 'error');
        return;
    }

    const modal = document.getElementById('delete-jpgs-modal');
    const message = document.getElementById('delete-jpgs-modal-message');

    let messageText = `¿Eliminar JPGs de ${jpgRawPhotos.length} foto(s) (manteniendo RAW)?\n\n`;
    messageText += `Esto eliminará solo los archivos JPG de las fotos que tienen RAW.\n`;

    if (jpgOnlyPhotos.length > 0) {
        messageText += `\n⚠️ ${jpgOnlyPhotos.length} foto(s) marcada(s) son JPG huérfano(s) y NO serán eliminadas.\n`;
    }

    messageText += `\nEsta acción no se puede deshacer.`;

    message.textContent = messageText;
    message.style.whiteSpace = 'pre-line';
    modal.style.display = 'flex';
}

function hideDeleteJpgsModal() {
    document.getElementById('delete-jpgs-modal').style.display = 'none';
}

async function deleteJpgs() {
    try {
        showLoading(true);
        hideDeleteJpgsModal();

        // Get marked photos that have both JPG and RAW
        const markedPhotos = Array.from(state.markedPhotos).map(index => state.photos[index]);
        const jpgRawPhotos = markedPhotos.filter(photo => photo.type === 'jpg+raw');

        const response = await fetch('/api/delete-jpgs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: jpgRawPhotos
            })
        });

        const result = await response.json();

        if (result.success) {
            let message = `${result.deleted} JPG(s) eliminado(s) correctamente`;
            if (result.skipped > 0) {
                message += ` (${result.skipped} omitido(s))`;
            }
            showToast(message, 'success');
            // Reload current folder
            await navigateToFolder(state.currentPath);
        } else {
            showToast(result.error || 'Error eliminando JPGs', 'error');
        }
    } catch (error) {
        showToast('Error eliminando JPGs', 'error');
        console.error(error);
    } finally {
        showLoading(false);
    }
}

// View Toggle
function toggleView() {
    if (state.currentView === 'grid') {
        if (state.photos.length > 0) {
            showCarousel(0);
        }
    } else {
        closeCarousel();
    }
}

function closeCarousel() {
    state.currentView = 'grid';
    document.getElementById('carousel-view').classList.remove('active');
    document.getElementById('revisor-panel').style.display = 'flex';
}

// Keyboard Shortcuts
function handleKeyboard(e) {
    if (state.currentView !== 'carousel') return;

    switch(e.key) {
        case 'ArrowLeft':
            e.preventDefault();
            navigateCarousel(-1);
            break;
        case 'ArrowRight':
            e.preventDefault();
            navigateCarousel(1);
            break;
        case ' ':
            e.preventDefault();
            toggleMark(state.currentCarouselIndex);
            break;
        case 'g':
        case 'G':
        case 'Escape':
            e.preventDefault();
            toggleView();
            break;
    }
}

// Lazy Loading
function handleScroll(e) {
    const grid = e.target;

    if (grid.scrollHeight - grid.scrollTop <= grid.clientHeight + 100) {
        if (state.loadedPhotos < state.photos.length) {
            state.loadedPhotos += 50;
            renderPhotos(state.photos);
        }
    }
}

// Update Counters
function updateCounters() {
    const markedCount = state.markedPhotos.size;
    const totalCount = state.photos.length;

    // Actualizar contador en panel de fotos
    document.getElementById('marked-count').textContent = `${markedCount} marcadas`;

    // Actualizar botones de acción
    if (state.isReviewFolder) {
        const restoreBtn = document.getElementById('restore-photos');
        const deleteBtn = document.getElementById('delete-photos');
        if (restoreBtn) restoreBtn.textContent = `Restaurar ${markedCount} fotos`;
        if (deleteBtn) deleteBtn.textContent = `Eliminar ${markedCount} fotos definitivamente`;
    } else {
        const moveBtn = document.getElementById('move-photos');
        if (moveBtn) moveBtn.textContent = `Mover ${markedCount} fotos a revisión`;
    }

    // Actualizar contador en carrusel
    if (state.currentView === 'carousel') {
        document.getElementById('carousel-counter').textContent =
            `Foto ${state.currentCarouselIndex + 1} de ${totalCount} - ${markedCount} marcadas`;
    }
}

// UI Helpers
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'flex' : 'none';
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Load and display app version
async function loadVersion() {
    try {
        const response = await fetch('/api/version');
        const data = await response.json();
        document.getElementById('app-version').textContent =
            `${data.name} v${data.version}`;
    } catch (error) {
        console.error('Error loading version:', error);
    }
}
