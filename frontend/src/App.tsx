import { useEffect, useState } from "react";
import { api, getToken, type User } from "./api";
import { Login } from "./components/Login";
import { Dashboard } from "./components/Dashboard";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          setUser(await api.me());
        } catch {
          setUser(null);
        }
      }
      setChecked(true);
    })();
  }, []);

  if (!checked) return null;

  if (!user) {
    return <Login onLoggedIn={setUser} />;
  }

  return <Dashboard user={user} onLogout={() => setUser(null)} />;
}
