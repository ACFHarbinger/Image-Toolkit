import React, { useState } from "react";
import { Plus, Minus } from "lucide-react";

interface OptionalFieldProps {
  title: string;
  children: React.ReactNode;
  startOpen?: boolean;
}

export const OptionalField: React.FC<OptionalFieldProps> = ({
  title,
  children,
  startOpen = false,
}) => {
  const [isOpen, setIsOpen] = useState(startOpen);

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {/* Header Frame */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: "flex",
          alignItems: "center",
          padding: "3px 6px",
          border: "1px solid #40444b", // Approximate Palette.Mid
          borderRadius: "3px",
          backgroundColor: "#2c2f33", // Approximate Palette.Base
          cursor: "pointer",
          marginBottom: isOpen ? "5px" : "0",
          transition: "background-color 0.2s",
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.backgroundColor = "#32353b")
        } // lighter hover
        onMouseLeave={(e) =>
          (e.currentTarget.style.backgroundColor = "#2c2f33")
        }
      >
        <button
          style={{
            background: "transparent",
            border: "none",
            color: "#dcddde", // Palette.Text
            marginRight: "8px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
          }}
        >
          {isOpen ? <Minus size={14} /> : <Plus size={14} />}
        </button>
        <span style={{ color: "#dcddde", fontWeight: 600, userSelect: "none" }}>
          {title}
        </span>
      </div>

      {/* Inner Widget */}
      {isOpen && <div>{children}</div>}
    </div>
  );
};
