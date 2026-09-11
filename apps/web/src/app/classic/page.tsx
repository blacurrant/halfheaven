import { redirect } from "next/navigation";

/** The chat-driven studio grew into the page at the root; its chat, caption
 *  fixer and timeline now live behind Edit there. */
export default function Classic() {
  redirect("/");
}
