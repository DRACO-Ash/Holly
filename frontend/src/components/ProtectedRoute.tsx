import { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

interface Props {
  children?: ReactNode;
}

// Where a user whose password an admin set is sent until they choose their own. A convenience:
// the server refuses everything else meanwhile.
const CHANGE_PATH = "/password";

export default function ProtectedRoute({ children }: Readonly<Props>) {
  const { isAuthenticated, user } = useAuth();
  const { pathname } = useLocation();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.must_change_password && pathname !== CHANGE_PATH) {
    return <Navigate to={CHANGE_PATH} replace />;
  }
  return <>{children ?? <Outlet />}</>;
}
