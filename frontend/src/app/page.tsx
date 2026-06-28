import { redirect } from "next/navigation";

export default function HomePage() {
  // MVP: por ahora redirigimos a Delta. Cuando agreguemos auth + selector,
  // acá listamos los lodges accesibles al user.
  redirect("/lodges/DEL/dashboard");
}
