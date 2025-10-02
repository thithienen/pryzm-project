import React, { useState, useCallback, useEffect, useRef } from 'react';
import './ResizableDivider.css';

const ResizableDivider = ({ onResize }) => {
  const dividerRef = useRef(null);
  const isDraggingRef = useRef(false);
  const [hasBeenDragged, setHasBeenDragged] = useState(false);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    isDraggingRef.current = true;
    setHasBeenDragged(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  const handleMouseMove = useCallback((e) => {
    if (!isDraggingRef.current) return;

    // Calculate the new width for the sources pane based on mouse position
    const containerWidth = window.innerWidth;
    const maxWidth = 1400; // Max width of main-layout
    const actualContainerWidth = Math.min(containerWidth, maxWidth);
    
    // Calculate position from the right edge
    const rightEdge = (containerWidth - actualContainerWidth) / 2 + actualContainerWidth;
    const distanceFromRight = rightEdge - e.clientX;
    
    // Constrain the sources pane width between 300px and 700px
    const newSourcesWidth = Math.max(300, Math.min(700, distanceFromRight));
    
    onResize(newSourcesWidth);
  }, [onResize]);

  const handleMouseUp = useCallback(() => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  }, []);

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  return (
    <div
      ref={dividerRef}
      className="resizable-divider"
      onMouseDown={handleMouseDown}
      title="Drag to resize"
    >
      <div className="divider-handle">
        <div className="divider-line"></div>
        {!hasBeenDragged && (
          <div className="divider-arrows">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 8L3 8M3 8L5 6M3 8L5 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M10 8L13 8M13 8L11 6M13 8L11 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        )}
      </div>
    </div>
  );
};

export default ResizableDivider;
