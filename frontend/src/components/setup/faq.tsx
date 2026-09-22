"use client";
import { useState } from "react";
import { MessageCircleQuestion, Plus, Trash2 } from "lucide-react";
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
              <li key={f.id} className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
                <div>
                  <p className="font-medium">{f.question}</p>
                  <p className="text-sm text-muted-foreground">{f.answer}</p>
                </div>
                <Button variant="ghost" size="icon" aria-label={`Remove "${f.question}"`}
                  disabled={remove.isPending} onClick={() => remove.mutate(f.id)}>
                  <Trash2 />
                </Button>
              </li>
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
