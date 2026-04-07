import { useState, useEffect, useRef } from 'react';

export function useWebSocket(jobId) {
  const [events, setEvents] = useState([]);
  const [phase, setPhase] = useState('upload');
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const ws = useRef(null);

  useEffect(() => {
    if (!jobId) return;

    ws.current = new WebSocket(`ws://localhost:8000/ws/${jobId}`);

    ws.current.onopen = () => {
      setIsConnected(true);
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [...prev, data]);
      setPhase(data.phase);
      setLastEvent(data);
    };

    ws.current.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [jobId]);

  return { events, phase, isConnected, lastEvent };
}
