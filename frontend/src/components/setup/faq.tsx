"use client";
import { useState } from "react";
import { MessageCircleQuestion, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useClinicChange } from "@/lib/queries";
import { Field } from "./field";
import { Section } from "./section";

export function Faq({ clinic }: { clinic: Schemas["Clinic"] }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const path = { params: { path: { clinic_id: clinic.id } } };
  const add = useClinicChange(clinic.id, (body: Schemas["FaqIn"]) =>
    unwrap(api.POST("/api/clinics/{clinic_id}/faq", { ...path, body })), "Answer added");
  const remove = useClinicChange(clinic.id, (faqId: number) =>
    unwrap(api.DELETE("/api/clinics/{clinic_id}/faq/{faq_id}", { params: { path: { clinic_id: clinic.id, faq_id: faqId } } })),
    "Answer removed");

  return (
    <div className="space-y-6">
      <Section title="Answers the receptionist gives"
        description="Common questions (parking, payment, what to bring). The receptionist answers only from these and the clinic details.">
        {clinic.faq.length === 0 ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <MessageCircleQuestion className="size-4" aria-hidden /> None yet. Add the questions patients ask most.
          </p>
        ) : (
          <ul className="divide-y">
            {clinic.faq.map((f) => (
              <FaqRow key={f.id} clinicId={clinic.id} faq={f} removing={remove.isPending} onRemove={() => remove.mutate(f.id)} />
            ))}
          </ul>
        )}
      </Section>
      <Section title="Add an answer">
        <form className="space-y-4" onSubmit={(e) => {
          e.preventDefault();
          add.mutate({ question: question.trim(), answer: answer.trim() }, { onSuccess: () => { setQuestion(""); setAnswer(""); } });
        }}>
          <Field id="question" label="Question">
            <Input id="question" required maxLength={300} placeholder="Do you accept UPI?" value={question} onChange={(e) => setQuestion(e.target.value)} />
          </Field>
          <Field id="answer" label="Answer">
            <Textarea id="answer" required maxLength={1000} rows={2} placeholder="Yes, cash, UPI and cards are all accepted."
              value={answer} onChange={(e) => setAnswer(e.target.value)} />
          </Field>
          <div className="flex justify-end">
            <Button type="submit" disabled={add.isPending}><Plus /> Add answer</Button>
          </div>
        </form>
      </Section>
    </div>
  );
}

/** One answer: read, or edited in place (no delete and retype). */
function FaqRow({ clinicId, faq, removing, onRemove }: {
  clinicId: number; faq: Schemas["Faq"]; removing: boolean; onRemove: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [question, setQuestion] = useState(faq.question);
  const [answer, setAnswer] = useState(faq.answer);
  const save = useClinicChange(clinicId, (body: Schemas["FaqIn"]) =>
    unwrap(api.PUT("/api/clinics/{clinic_id}/faq/{faq_id}", { params: { path: { clinic_id: clinicId, faq_id: faq.id } }, body })),
    "Answer saved");
  const cancel = () => { setQuestion(faq.question); setAnswer(faq.answer); setEditing(false); };

  if (editing) {
    const id = `faq${faq.id}`;
    return (
      <li className="py-3 first:pt-0 last:pb-0">
        <form className="space-y-3" onSubmit={(e) => {
          e.preventDefault();
          save.mutate({ question: question.trim(), answer: answer.trim() }, { onSuccess: () => setEditing(false) });
        }}>
          <Field id={`${id}-q`} label="Question">
            <Input id={`${id}-q`} required maxLength={300} autoFocus value={question} onChange={(e) => setQuestion(e.target.value)} />
          </Field>
          <Field id={`${id}-a`} label="Answer">
            <Textarea id={`${id}-a`} required maxLength={1000} rows={2} value={answer} onChange={(e) => setAnswer(e.target.value)} />
          </Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={cancel}>Cancel</Button>
            <Button type="submit" disabled={save.isPending || (question.trim() === faq.question && answer.trim() === faq.answer)}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </li>
    );
  }
  return (
    <li className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <div>
        <p className="font-medium">{faq.question}</p>
        <p className="text-sm text-muted-foreground">{faq.answer}</p>
      </div>
      <div className="flex shrink-0">
        <Button variant="ghost" size="icon" aria-label={`Edit "${faq.question}"`} onClick={() => setEditing(true)}>
          <Pencil />
        </Button>
        <Button variant="ghost" size="icon" aria-label={`Remove "${faq.question}"`} disabled={removing} onClick={onRemove}>
          <Trash2 />
        </Button>
      </div>
    </li>
  );
}
