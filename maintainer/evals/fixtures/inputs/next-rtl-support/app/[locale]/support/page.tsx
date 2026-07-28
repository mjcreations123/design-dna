type Locale = "en" | "ar";

const copy = {
  en: {
    title: "Request support",
    intro: "This local demo does not send data.",
    name: "Name",
    email: "Email",
    message: "How can we help?",
    submit: "Review request"
  },
  ar: {
    title: "طلب الدعم",
    intro: "هذا نموذج محلي ولا يرسل البيانات.",
    name: "الاسم",
    email: "البريد الإلكتروني",
    message: "كيف يمكننا المساعدة؟",
    submit: "مراجعة الطلب"
  }
} as const;

export default function SupportPage({
  params
}: {
  params: {locale: string};
}) {
  const locale: Locale = params.locale === "ar" ? "ar" : "en";
  const direction = locale === "ar" ? "rtl" : "ltr";
  const text = copy[locale];

  return (
    <main className="support-shell">
      <p className="eyebrow">Support fixture</p>
      <h1>{text.title}</h1>
      <p>{text.intro}</p>

      <form className="support-form">
        <label>
          <span>{text.name}</span>
          <input name="name" />
        </label>
        <label>
          <span>{text.email}</span>
          <input name="email" />
        </label>
        <label>
          <span>{text.message}</span>
          <textarea name="message" rows={5} />
        </label>
        <button>{text.submit}</button>
      </form>
    </main>
  );
}
