class WebSocketService {
    constructor() {
        this.ws = null;
        this.listeners = new Set();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this._heartbeatInterval = null;
    }

    _getUrl() {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        return `${proto}://${window.location.host}/ws`;
    }

    _startHeartbeat() {
        this._stopHeartbeat();
        this._heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send('ping');
            }
        }, 20000); // Send ping every 20 seconds to keep connection alive
    }

    _stopHeartbeat() {
        if (this._heartbeatInterval) {
            clearInterval(this._heartbeatInterval);
            this._heartbeatInterval = null;
        }
    }

    connect() {
        const url = this._getUrl();
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('WS Connected');
            this.reconnectAttempts = 0;
            this._startHeartbeat();
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.listeners.forEach((listener) => listener(data));
            } catch (e) {
                // Ignore non-JSON messages (e.g. pong)
            }
        };

        this.ws.onclose = () => {
            console.log('WS Disconnected');
            this._stopHeartbeat();
            this.reconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WS Error', error);
            this._stopHeartbeat();
            this.ws.close();
        };
    }

    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
                console.log('Reconnecting WS...');
                this.reconnectAttempts++;
                this.connect();
            }, 3000);
        }
    }

    subscribe(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    disconnect() {
        this._stopHeartbeat();
        if (this.ws) {
            this.ws.close();
        }
    }
}

export const wsService = new WebSocketService();
