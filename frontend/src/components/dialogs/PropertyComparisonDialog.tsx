import React from "react";

interface PropertyComparisonDialogProps {
  isOpen: boolean;
  onClose: () => void;
  propertyData: Array<Record<string, any>>;
}

export const PropertyComparisonDialog: React.FC<
  PropertyComparisonDialogProps
> = ({ isOpen, onClose, propertyData }) => {
  if (!isOpen) return null;

  // Logic to sort keys based on priority
  const priorityOrder = [
    "File Size",
    "Width",
    "Height",
    "Format",
    "Mode",
    "Last Modified",
    "Created",
    "Path",
    "Error",
  ];

  const allKeys = new Set<string>();
  propertyData.forEach((item) =>
    Object.keys(item).forEach((k) => allKeys.add(k)),
  );

  const sectionKeys = priorityOrder.filter((k) => allKeys.has(k));
  Array.from(allKeys)
    .sort()
    .forEach((k) => {
      if (!sectionKeys.includes(k) && k !== "File Name") {
        sectionKeys.push(k);
      }
    });

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.7)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 2000,
      }}
    >
      <div
        style={{
          backgroundColor: "#36393f",
          color: "#dcddde",
          padding: "20px",
          borderRadius: "8px",
          width: "600px",
          maxHeight: "80vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Image Property Comparison</h3>

        <div
          style={{ overflowY: "auto", flex: 1, border: "1px solid #202225" }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "14px",
            }}
          >
            <thead>
              <tr style={{ backgroundColor: "#202225", textAlign: "left" }}>
                <th style={{ padding: "8px" }}>Property</th>
                <th style={{ padding: "8px" }}>Image File</th>
                <th style={{ padding: "8px" }}>Value</th>
              </tr>
            </thead>
            <tbody>
              {propertyData.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    style={{ padding: "10px", textAlign: "center" }}
                  >
                    No Images Selected
                  </td>
                </tr>
              ) : (
                sectionKeys.flatMap((key, keyIdx) => {
                  const bgColor = keyIdx % 2 === 0 ? "#2c2f33" : "#23272a";
                  return propertyData.map((item, itemIdx) => {
                    const imgName =
                      item["File Name"] ||
                      item["Path"]?.split(/[/\\]/).pop() ||
                      "Unknown";
                    const val = String(item[key] || "N/A");
                    return (
                      <tr
                        key={`${key}-${itemIdx}`}
                        style={{ backgroundColor: bgColor }}
                      >
                        <td style={{ padding: "6px 8px", fontWeight: "bold" }}>
                          {key}
                        </td>
                        <td style={{ padding: "6px 8px" }}>{imgName}</td>
                        <td style={{ padding: "6px 8px", textAlign: "center" }}>
                          {val}
                        </td>
                      </tr>
                    );
                  });
                })
              )}
            </tbody>
          </table>
        </div>

        <div
          style={{
            marginTop: "15px",
            display: "flex",
            justifyContent: "flex-end",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "8px 16px",
              backgroundColor: "#5865f2",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
