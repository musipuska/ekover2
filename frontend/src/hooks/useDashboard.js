import { useContext } from "react";

import { DashboardContext } from "../context/DashboardContext";

export function useDashboard() {
  const value = useContext(DashboardContext);
  if (!value) throw new Error("useDashboard должен использоваться внутри DashboardProvider");
  return value;
}
