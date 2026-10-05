// Warden gateway on Cloudflare Workers.
//
// VERIFIED against Cloudflare Workers AI, Vectorize and AI Gateway docs on the
// date in the guide. NOT yet run against a real account. This is the same
// eight-control pipeline as the offline Python gateway, moved to the edge:
// the model, the vector store and the safety classifier are Cloudflare
// bindings, and the tool policy is the same allow / block / ask rules.
//
// Bindings expected in wrangler.toml: AI (Workers AI), VEC (Vectorize),
// and the vars COMPANY_DOMAIN, CANARY.

const GUARD = "@cf/meta/llama-guard-3-8b";
const CHAT = "@cf/zai-org/glm-4.7-flash";
const EMBED = "@cf/baai/bge-base-en-v1.5";

// region: worker_retrieve
// W5: retrieve only the chunks the caller may read. The acl_group filter runs
// INSIDE the Vectorize query with $in, so a document the caller is not
// entitled to never comes back. The metadata index on acl_group must be
// created before any vector is upserted, or older vectors are not filterable.
async function retrieve(env, question, allowedGroups) {
  const embedding = await env.AI.run(EMBED, { text: [question] });
  const vector = embedding.data[0];
  const matches = await env.VEC.query(vector, {
    topK: 5,
    returnMetadata: "all",
    filter: { acl_group: { $in: allowedGroups } },
  });
  return matches.matches || [];
}
// endregion: worker_retrieve

// region: worker_tool_policy
// W8: the same allow / block / ask rules as the Python engine. An email may
// only go to the company domain; a payroll change over a threshold needs a
// human; a side effect the user did not ask for is never run silently.
const COMPANY = "peoplecraft.example";
const ASK_ABOVE = 500;
const BLOCK_ABOVE = 10000;

function decideTool(name, args, principal) {
  if (name === "email_document") {
    const to = String(args.to || "").toLowerCase();
    const domain = to.includes("@") ? to.split("@").pop() : "";
    if (domain !== COMPANY) {
      return { outcome: "block", reason: `recipient ${to} is not on ${COMPANY}` };
    }
    return { outcome: "allow", reason: "internal recipient" };
  }
  if (name === "raise_payroll_change") {
    if (principal.role !== "payroll_officer") {
      return { outcome: "block", reason: `role ${principal.role} may not change pay` };
    }
    const amount = Math.abs(Number(args.amount_gbp) || 0);
    if (amount > BLOCK_ABOVE) return { outcome: "block", reason: "above hard ceiling" };
    if (amount > ASK_ABOVE) return { outcome: "ask", reason: "needs a second person" };
    return { outcome: "allow", reason: "within limit" };
  }
  return { outcome: "allow", reason: "read-only tool" };
}
// endregion: worker_tool_policy

// Workers AI models answer in one of two shapes. Older chat models return
// { response: "..." }; newer OpenAI-compatible ones (glm-4.7-flash among them)
// return { choices: [{ message: { content: "..." } }] }. Read either.
function chatText(out) {
  if (out && typeof out.response === "string") return out.response;
  const message = out && out.choices && out.choices[0] && out.choices[0].message;
  return (message && message.content) || "";
}

// Llama Guard's verdict comes back either as text ("safe", or "unsafe" and the
// categories) or as an object { safe: false, categories: [...] }. Read either.
function guardSaysUnsafe(out) {
  const verdict = out && out.response;
  if (verdict && typeof verdict === "object") return verdict.safe === false;
  return String(verdict || "").trim().toLowerCase().startsWith("unsafe");
}

// region: worker_fetch
export default {
  async fetch(request, env) {
    const { question, principal } = await request.json();

    // W3: Llama Guard on the input.
    const guard = await env.AI.run(GUARD, {
      messages: [{ role: "user", content: question }],
    });
    if (guardSaysUnsafe(guard)) {
      return Response.json({ decision: "block", reason: "W3 harmful request" });
    }

    // W5: permission-aware retrieval, then W4 (documents were masked at ingest).
    const hits = await retrieve(env, question, principal.grants);
    const context = hits.map((h) => `[${h.id}] ${h.metadata.text}`).join("\n");

    // The model, with the hardened system prompt that carries the canary.
    const answer = await env.AI.run(CHAT, {
      messages: [
        { role: "system", content: env.SYSTEM_PROMPT },
        { role: "user", content: context + "\n\nQuestion: " + question },
      ],
    });
    let text = chatText(answer);

    // W7: block a system prompt leak by its canary.
    if (text.includes(env.CANARY)) {
      return Response.json({ decision: "block", reason: "W7 canary leak" });
    }
    // W8 would run here on any tool_calls the model returned, using decideTool.
    return Response.json({ decision: "allow", answer: text });
  },
};
// endregion: worker_fetch
