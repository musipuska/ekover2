import React from "react";

export default function StatCard({
  title,
  value,
  description,
  icon: Icon,
}) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span>{title}</span>

        <div className="stat-icon">
          <Icon size={21} />
        </div>
      </div>

      <div className="stat-value">{value}</div>

      <div className="stat-description">
        {description}
      </div>
    </div>
  );
}