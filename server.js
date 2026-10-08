import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import cors from 'cors';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 10000;

app.use(cors());
app.use(express.json());

// Serve static Vite output from dist/
app.use(express.static(path.join(__dirname, 'dist')));

// Secure Gemini API Proxy endpoint
app.post('/api/gemini', async (req, res) => {
  const { prompt, isEnglish, isOfficer } = req.body;
  const apiKey = process.env.GEMINI_API_KEY;

  if (!apiKey) {
    console.error("Missing GEMINI_API_KEY environment variable on server.");
    return res.status(500).json({ error: "Gemini API key is not configured on the server." });
  }

  const systemContext = isOfficer
    ? `You are the official Gram Panchayat Officer AI Assistant for Loni Kalbhor (लोणी काळभोर) village, Pune, Maharashtra.
Panchayat Core Metrics:
- Active Citizens: 10
- Logged Grievances: 5 (1 Critical in Ward 3, 2 High)
- Capital Infrastructure Projects: 4 (Concrete Road construction in Ward 3 is Delayed at 68% progress, Budget 10 Lakhs; Digital Center Setup in Ward 2 is Completed at 100% progress, Budget 3.5 Lakhs; Water Tank & Pipeline in Ward 1 is Ongoing at 45% progress, Budget 15 Lakhs; Primary School Boundary Wall & Smart Classroom in Ward 3/4 is Ongoing at 90% progress, Budget 6 Lakhs)
- Next Sabha Meeting: August 20, 2026, at ZP School Ground.
User query: "${prompt}"
Language: ${isEnglish ? 'English' : 'Marathi'}.
Please formulate a highly helpful, concise, and professional answer for the Panchayat Officer in the requested language. Keep it under 4 sentences. Use markdown bold where appropriate.`
    : `You are the official E-Panchayat GraphRAG AI Assistant for Loni Kalbhor (लोणी काळभोर) village, Pune, Maharashtra.
Panchayat Status:
- Citizens Registered: 10 (including Savita Patil, Amit Shinde, Anandrao Patil)
- Infrastructure Projects: 4 (Concrete Road construction in Ward 3 is Delayed at 68% progress, Budget 10 Lakhs; Digital Center Setup in Ward 2 is Completed at 100% progress, Budget 3.5 Lakhs; Water Tank & Pipeline in Ward 1 is Ongoing at 45% progress, Budget 15 Lakhs; Primary School Boundary Wall & Smart Classroom in Ward 3/4 is Ongoing at 90% progress, Budget 6 Lakhs)
- Unresolved Grievances: 5 (Water pipeline leakage near Maruti Temple, drainage clogging)
- Next Sabha Meeting: August 20, 2026, at ZP School Ground.
User query: "${prompt}"
Language: ${isEnglish ? 'English' : 'Marathi'}.
Please formulate a highly helpful, brief, and professional response in the requested language. Keep it under 4 sentences. Use markdown bold where appropriate.`;

  try {
    const apiRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: systemContext }] }]
      })
    });

    if (!apiRes.ok) {
      const errText = await apiRes.text();
      console.error(`Gemini API returned status ${apiRes.status}:`, errText);
      return res.status(apiRes.status).json({ error: `Gemini API returned status ${apiRes.status}` });
    }

    const data = await apiRes.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text || "";
    res.json({ text });
  } catch (err) {
    console.error("Server-side Gemini call failed:", err);
    res.status(500).json({ error: "Failed to connect to Gemini API." });
  }
});

// Fallback all other GET requests to index.html for Single Page Application Router
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
