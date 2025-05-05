document.addEventListener('DOMContentLoaded', function() {
    // Cargar el historial al iniciar
    loadUrlHistory();

    // Manejador del formulario
    document.getElementById('shortenForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const urlInput = document.getElementById('urlInput').value.trim();
        const resultDiv = document.getElementById('result');

        if (!urlInput) {
            resultDiv.innerHTML = '<p style="color: red;">Por favor ingresa una URL</p>';
            return;
        }

        try {
            const response = await fetch('/api/shorten', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: urlInput }),
            });

            const data = await response.json();

            if (response.ok) {
                // Mostrar resultado
                resultDiv.innerHTML = `
                    <p><strong>URL original:</strong> <a href="${data.original_url}" target="_blank">${truncateText(data.original_url, 50)}</a></p>
                    <p><strong>URL acortada:</strong> <a href="${data.short_url}" target="_blank">${data.short_url}</a></p>
                    <button onclick="copyToClipboard('${data.short_url}')">Copiar</button>
                `;
                
                // Actualizar el historial
                await loadUrlHistory();
                
                // Limpiar el input
                document.getElementById('urlInput').value = '';
            } else {
                resultDiv.innerHTML = `<p style="color: red;">Error: ${data.error || 'Error desconocido'}</p>`;
            }
        } catch (error) {
            resultDiv.innerHTML = `<p style="color: red;">Error de conexión: ${error.message}</p>`;
        }
    });
});

// Función para cargar el historial de URLs
async function loadUrlHistory() {
    try {
        const response = await fetch('/api/urls');
        const urls = await response.json();
        const historyList = document.getElementById('urlHistory');
        
        if (urls.length === 0) {
            historyList.innerHTML = '<li>No hay URLs acortadas aún</li>';
            return;
        }
        
        historyList.innerHTML = urls.map(url => `
            <li>
                <div class="url-entry">
                    <p><strong>Original:</strong> <a href="${url.original}" target="_blank">${truncateText(url.original, 40)}</a></p>
                    <p><strong>Acortada:</strong> <a href="${url.short}" target="_blank">${url.short}</a></p>
                    <button onclick="copyToClipboard('${url.short}')">Copiar</button>
                </div>
            </li>
        `).join('');
    } catch (error) {
        console.error('Error cargando historial:', error);
    }
}

// Función para acortar texto largo
function truncateText(text, maxLength) {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// Función para copiar al portapapeles
function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => {
            alert('URL copiada: ' + text);
        })
        .catch(err => {
            console.error('Error al copiar:', err);
            // Fallback para navegadores antiguos
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            alert('URL copiada!');
        });
}