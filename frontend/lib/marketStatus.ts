export interface MarketStatus {
  isOpen: boolean;
  message: string;
}

// Known NSE Holidays (Format: YYYY-MM-DD)
// Only listing weekday holidays as weekends are already handled.
const NSE_HOLIDAYS = new Set([
  // 2024
  "2024-01-22", // Special Holiday
  "2024-01-26", // Republic Day
  "2024-03-08", // Mahashivratri
  "2024-03-25", // Holi
  "2024-03-29", // Good Friday
  "2024-04-11", // Id-Ul-Fitr (Ramzan Id)
  "2024-04-17", // Ram Navami
  "2024-05-01", // Maharashtra Day
  "2024-05-20", // General Elections (Mumbai)
  "2024-06-17", // Bakri Id
  "2024-07-17", // Muharram
  "2024-08-15", // Independence Day
  "2024-10-02", // Mahatma Gandhi Jayanti
  "2024-11-01", // Diwali (Laxmi Pujan)
  "2024-11-15", // Gurunanak Jayanti
  "2024-11-20", // Assembly Elections (Maharashtra)
  "2024-12-25", // Christmas
  
  // 2025
  "2025-02-26", // Mahashivratri
  "2025-03-14", // Holi
  "2025-03-31", // Id-Ul-Fitr
  "2025-04-10", // Mahavir Jayanti
  "2025-04-14", // Dr. Baba Saheb Ambedkar Jayanti
  "2025-04-18", // Good Friday
  "2025-05-01", // Maharashtra Day
  "2025-06-06", // Bakri Id
  "2025-08-15", // Independence Day
  "2025-08-27", // Ganesh Chaturthi
  "2025-10-02", // Mahatma Gandhi Jayanti
  "2025-10-21", // Diwali
  "2025-10-22", // Diwali Balipratipada
  "2025-11-05", // Gurunanak Jayanti
  "2025-12-25", // Christmas

  // 2026
  "2026-01-26", // Republic Day
  "2026-02-13", // Mahashivratri
  "2026-03-03", // Holi
  "2026-03-20", // Id-Ul-Fitr
  "2026-04-03", // Good Friday
  "2026-04-14", // Dr. Baba Saheb Ambedkar Jayanti
  "2026-05-01", // Maharashtra Day
  "2026-05-27", // Bakri Id
  "2026-10-02", // Mahatma Gandhi Jayanti
  "2026-11-09", // Diwali
  "2026-12-25", // Christmas
]);

export function getMarketStatus(): MarketStatus {
  // Use Asia/Kolkata timezone to get accurate IST time
  const now = new Date();
  
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    weekday: 'long'
  });

  const parts = formatter.formatToParts(now);
  const getPart = (type: string) => parts.find(p => p.type === type)?.value || "";
  
  const year = getPart('year');
  const month = getPart('month');
  const day = getPart('day');
  const weekday = getPart('weekday');
  const hour = parseInt(getPart('hour'), 10);
  const minute = parseInt(getPart('minute'), 10);

  const currentDateString = `${year}-${month}-${day}`;

  // Check Weekends
  if (weekday === "Saturday" || weekday === "Sunday") {
    return { isOpen: false, message: "Weekend" };
  }

  // Check Holidays
  if (NSE_HOLIDAYS.has(currentDateString)) {
    return { isOpen: false, message: "Market Holiday" };
  }

  // Check Market Hours (09:15 to 15:30 IST)
  const currentMinutes = hour * 60 + minute;
  const marketOpenMinutes = 9 * 60 + 15;
  const marketCloseMinutes = 15 * 60 + 30;

  if (currentMinutes < marketOpenMinutes) {
    return { isOpen: false, message: "Opens at 09:15 AM" };
  }

  if (currentMinutes >= marketCloseMinutes) {
    return { isOpen: false, message: "Closed" };
  }

  return { isOpen: true, message: "Live" };
}
