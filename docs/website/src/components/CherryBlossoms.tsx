import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

const Petal = ({ delay, duration, startX, startY, scale }: { delay: number, duration: number, startX: number, startY: number, scale: number }) => {
  return (
    <motion.div
      initial={{ x: startX, y: startY, rotate: 0, opacity: 0 }}
      animate={{
        x: startX - (Math.random() * 200 + 100),
        y: startY + (Math.random() * 400 + 400),
        rotate: Math.random() * 360,
        opacity: [0, 0.8, 0.8, 0],
      }}
      transition={{
        duration: duration,
        delay: delay,
        repeat: Infinity,
        ease: 'linear',
      }}
      style={{
        position: 'absolute',
        width: `${12 * scale}px`,
        height: `${12 * scale}px`,
        background: 'linear-gradient(135deg, #ffb7c5, #e83e8c)',
        borderRadius: '0 50% 50% 50%',
        transformOrigin: 'center',
        boxShadow: '0 0 10px rgba(232, 62, 140, 0.3)',
        zIndex: 0,
        pointerEvents: 'none',
      }}
    />
  );
};

type PetalData = {
  id: number;
  delay: number;
  duration: number;
  startX: number;
  startY: number;
  scale: number;
};

export default function CherryBlossoms() {
  const [petals, setPetals] = useState<PetalData[]>([]);

  useEffect(() => {
    // Generate petals only on client to avoid hydration mismatch
    const newPetals = Array.from({ length: 35 }).map((_, i) => ({
      id: i,
      delay: Math.random() * 15,
      duration: Math.random() * 10 + 15,
      startX: Math.random() * window.innerWidth + 200,
      startY: Math.random() * -200 - 50,
      scale: Math.random() * 0.8 + 0.4,
    }));
    setPetals(newPetals);
  }, []);

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {petals.map(p => (
        <Petal key={p.id} {...p} />
      ))}
    </div>
  );
}
