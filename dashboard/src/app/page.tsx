"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  User,
  MapPin,
  Building,
  CheckCircle2,
  Clock,
  AlertCircle,
  Filter,
  Moon,
  Sun,
  ChevronLeft,
  ChevronRight,
  Download,
  RefreshCw,
  FileSpreadsheet,
  TrendingUp,
  BarChart3,
  PieChart,
  X,
  Layers,
  ChevronDown,
  FileText,
  Send,
  XCircle
} from "lucide-react";

// Types for CSV records
interface ScraperRecord {
  searchedEmail: string;
  idCode: string;
  name: string;
  address: string;
  buildingNo: string;
  nib: string;
  email: string;
  scale: string;
  unitCount: string;
  postalCode: string;
  slsChange: string;
  idsbrUmkm: string;
  status: string;
  mode: string;
  officer: string;
  notes: string;
  nama_kec: string;
  koseka: string;
  isPrioritas: string;
}

const normalizeScale = (scaleStr: string): string => {
  if (!scaleStr) return "Keluarga";
  const s = scaleStr.trim().toUpperCase();
  if (!s || s === "-" || s === "TIDAK TERIDENTIFIKASI") return "Keluarga";
  if (s.includes("DUMMY")) return "UMKM/Dummy";
  if (s.includes("BANGUNAN_LAIN") || s.includes("BANGUNAN LAIN")) return "UMKM Bangunan Lain";
  if (s.includes("KELUARGA")) {
    if (s.includes("UMKM")) return "UMKM/Keluarga";
    return "Keluarga";
  }
  if (s.includes("UMK")) return "UMK";
  if (s === "UM") return "UM";
  if (s === "UB") return "UB";
  if (s.includes("UMKM")) return "UMKM/Keluarga";
  return "Keluarga";
};

// Interface for processed dashboard scraped data records
interface DashboardRecord {
  category: string;       // Pencacah or Pengawas
  email: string;          // Officer email
  slsCode: string;        // SLS Code
  open: number;           // OPEN count
  draft: number;          // DRAFT count
  submit: number;         // SUBMITTED BY Pencacah count
  reject: number;         // REJECTED BY Pengawas count
  approve: number;        // APPROVED BY Pengawas count
  namaPetugas: string;    // Name of officer
  jabatanPetugas: string; // PPL or PML
  namaKec: string;        // Kecamatan name
  koseka: string;         // Koseka name
}

const formatKecName = (name: string): string => {
  if (!name) return "-";
  let cleaned = name.replace(/\(\d+\)/g, "").trim();
  return cleaned
    .toLowerCase()
    .split(" ")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

const parseDashboardScrapedCSV = (csvText: string): DashboardRecord[] => {
  const lines = csvText.split("\n");
  const parsed: DashboardRecord[] = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const row: string[] = [];
    let insideQuote = false;
    let entry = "";

    for (let j = 0; j < line.length; j++) {
      const char = line[j];
      if (char === '"') {
        insideQuote = !insideQuote;
      } else if (char === "," && !insideQuote) {
        row.push(entry);
        entry = "";
      } else {
        entry += char;
      }
    }
    row.push(entry);

    if (row.length >= 8) {
      parsed.push({
        category: row[0].replace(/"/g, "").trim(),
        email: row[1].replace(/"/g, "").trim(),
        slsCode: row[2].replace(/"/g, "").trim(),
        open: parseInt(row[3]) || 0,
        draft: parseInt(row[4]) || 0,
        submit: parseInt(row[5]) || 0,
        reject: parseInt(row[6]) || 0,
        approve: parseInt(row[7]) || 0,
        namaPetugas: row[8] ? row[8].replace(/"/g, "").trim() : "",
        jabatanPetugas: row[9] ? row[9].replace(/"/g, "").trim() : "",
        namaKec: row[10] ? row[10].replace(/"/g, "").trim() : "",
        koseka: row[11] ? row[11].replace(/"/g, "").trim() : "",
      });
    }
  }
  return parsed;
};

export default function DashboardPage() {
  // Theme state
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Data states
  const [rawData, setRawData] = useState<ScraperRecord[]>([]);
  const [dashboardRawData, setDashboardRawData] = useState<DashboardRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  // Summary states from CSV files
  const [totalPrelistSummary, setTotalPrelistSummary] = useState<number>(0);
  const [summaryStatusCounts, setSummaryStatusCounts] = useState({
    open: 0,
    submit: 0,
    approve: 0,
    draft: 0,
    reject: 0
  });

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [scaleFilter, setScaleFilter] = useState("all");
  const [selectedOfficer, setSelectedOfficer] = useState("all");
  const [selectedSubdistrict, setSelectedSubdistrict] = useState("all");
  const [selectedKoseka, setSelectedKoseka] = useState("all");

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  // Double scrollbar refs and state
  const topScrollRef = useRef<HTMLDivElement>(null);
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const [tableWidth, setTableWidth] = useState(0);

  const isScrollingTop = useRef(false);
  const isScrollingTable = useRef(false);

  const handleTopScroll = () => {
    if (isScrollingTable.current) return;
    isScrollingTop.current = true;
    if (topScrollRef.current && tableContainerRef.current) {
      tableContainerRef.current.scrollLeft = topScrollRef.current.scrollLeft;
    }
    window.requestAnimationFrame(() => {
      isScrollingTop.current = false;
    });
  };

  const handleTableScroll = () => {
    if (isScrollingTop.current) return;
    isScrollingTable.current = true;
    if (tableContainerRef.current && topScrollRef.current) {
      topScrollRef.current.scrollLeft = tableContainerRef.current.scrollLeft;
    }
    window.requestAnimationFrame(() => {
      isScrollingTable.current = false;
    });
  };



  // Fetch and parse CSV data
  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch and parse ringkasan_Assign.csv
      try {
        const assignResponse = await fetch("/ringkasan_Assign.csv");
        if (assignResponse.ok) {
          const assignText = await assignResponse.text();
          const assignLines = assignText.split("\n").map(l => l.trim()).filter(Boolean);
          if (assignLines.length > 1) {
            const headers = assignLines[0].split(",");
            const values = assignLines[1].split(",");
            const assignedIdx = headers.indexOf("assigned");
            const haveNotAssignedIdx = headers.indexOf("have-not-assigned");
            let assigned = 0;
            let haveNotAssigned = 0;
            if (assignedIdx !== -1) assigned = parseInt(values[assignedIdx]) || 0;
            if (haveNotAssignedIdx !== -1) haveNotAssigned = parseInt(values[haveNotAssignedIdx]) || 0;
            setTotalPrelistSummary(assigned + haveNotAssigned);
          }
        }
      } catch (e) {
        console.warn("Gagal memuat ringkasan_Assign.csv, menggunakan data detail sebagai fallback:", e);
      }

      // Fetch and parse ringkasan_Progres.csv
      try {
        const progresResponse = await fetch("/ringkasan_Progres.csv");
        if (progresResponse.ok) {
          const progresText = await progresResponse.text();
          const progresLines = progresText.split("\n").map(l => l.trim()).filter(Boolean);
          if (progresLines.length > 1) {
            const headers = progresLines[0].split(",");
            const values = progresLines[1].split(",");
            const openIdx = headers.indexOf("OPEN");
            const submitIdx = headers.indexOf("SUBMITTED BY Pencacah");
            const draftIdx = headers.indexOf("DRAFT");
            const rejectIdx = headers.indexOf("REJECTED BY Pengawas");
            const approveIdx = headers.indexOf("APPROVED BY Pengawas");
            
            let openVal = 0, submitVal = 0, draftVal = 0, rejectVal = 0, approveVal = 0;
            if (openIdx !== -1) openVal = parseInt(values[openIdx]) || 0;
            if (submitIdx !== -1) submitVal = parseInt(values[submitIdx]) || 0;
            if (draftIdx !== -1) draftVal = parseInt(values[draftIdx]) || 0;
            if (rejectIdx !== -1) rejectVal = parseInt(values[rejectIdx]) || 0;
            if (approveIdx !== -1) approveVal = parseInt(values[approveIdx]) || 0;
            
            setSummaryStatusCounts({
              open: openVal,
              submit: submitVal,
              draft: draftVal,
              reject: rejectVal,
              approve: approveVal
            });
          }
        }
      } catch (e) {
        console.warn("Gagal memuat ringkasan_Progres.csv, menggunakan data detail sebagai fallback:", e);
      }
      
      const response = await fetch("/update_data.csv");
      if (!response.ok) {
        throw new Error("Gagal mengambil file update_data.csv. Pastikan file data hasil scrape tersedia.");
      }
      
      const text = await response.text();
      
      // Basic quote-aware CSV parser
      const parseCSV = (csvText: string): ScraperRecord[] => {
        const lines = csvText.split("\n");
        const parsed: ScraperRecord[] = [];
        
        for (let i = 1; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;
          
          const row: string[] = [];
          let insideQuote = false;
          let entry = "";
          
          for (let j = 0; j < line.length; j++) {
            const char = line[j];
            if (char === '"') {
              insideQuote = !insideQuote;
            } else if (char === "," && !insideQuote) {
              row.push(entry);
              entry = "";
            } else {
              entry += char;
            }
          }
          row.push(entry); // Push the last entry
          
          // Only add rows that have content and contain valid Kode Identitas
          if (row.length >= 16 && row[1] && row[1].trim() !== "" && row[1] !== "Kode Identitas") {
            parsed.push({
              searchedEmail: row[0].replace(/"/g, "").trim(),
              idCode: row[1].replace(/"/g, "").trim(),
              name: row[2].replace(/"/g, "").trim(),
              address: row[3].replace(/"/g, "").trim(),
              buildingNo: row[4].replace(/"/g, "").trim(),
              nib: row[5].replace(/"/g, "").trim(),
              email: row[6].replace(/"/g, "").trim(),
              scale: normalizeScale(row[7].replace(/"/g, "").trim()),
              unitCount: row[8].replace(/"/g, "").trim(),
              postalCode: row[9].replace(/"/g, "").trim(),
              slsChange: row[10].replace(/"/g, "").trim(),
              idsbrUmkm: row[11].replace(/"/g, "").trim(),
              status: row[12].replace(/"/g, "").trim() || "Kosong", // blank status is marked as 'Kosong'
              mode: row[13].replace(/"/g, "").trim(),
              officer: row[14].replace(/"/g, "").trim(),
              notes: row[15].replace(/"/g, "").trim(),
              nama_kec: row[16] ? row[16].replace(/"/g, "").trim() : "",
              koseka: row[17] ? row[17].replace(/"/g, "").trim() : "",
              isPrioritas: row[18] ? row[18].replace(/"/g, "").trim() : "Tidak",
            });
          }
        }
        return parsed;
      };

      const parsedRecords = parseCSV(text);
      setRawData(parsedRecords);

      // Fetch and parse dashboard_scraped_data.csv for Kecamatan realization ranking
      try {
        const dashboardResponse = await fetch("/dashboard_scraped_data.csv");
        if (dashboardResponse.ok) {
          const dashboardText = await dashboardResponse.text();
          const parsedDashboard = parseDashboardScrapedCSV(dashboardText);
          setDashboardRawData(parsedDashboard);
        }
      } catch (e) {
        console.warn("Gagal memuat dashboard_scraped_data.csv:", e);
      }
      
      // Set last updated time from text file, with fallback
      let loadedTimestamp = "";
      try {
        const timeResponse = await fetch("/last_updated.txt");
        if (timeResponse.ok) {
          loadedTimestamp = (await timeResponse.text()).trim();
        }
      } catch (e) {
        console.warn("Gagal mengambil file last_updated.txt, fallback ke waktu sekarang.");
      }
      
      if (loadedTimestamp) {
        setLastUpdated(loadedTimestamp);
      } else {
        const now = new Date();
        setLastUpdated(now.toLocaleDateString("id-ID", {
          day: "numeric",
          month: "long",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit"
        }) + " WITA");
      }
      
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Terjadi kesalahan saat memuat data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Compute overall stats
  const stats = useMemo(() => {
    const total = rawData.length;
    let openCount = 0;
    let draftCount = 0;
    let submitCount = 0;
    let rejectCount = 0;
    let approvedCount = 0;
    let emptyCount = 0;

    rawData.forEach(r => {
      const s = r.status.toLowerCase().trim();
      if (s === "open") {
        openCount++;
      } else if (s === "draft") {
        draftCount++;
      } else if (s === "submitted by pencacah" || s === "submit" || s === "submitted") {
        submitCount++;
      } else if (s === "rejected by pengawas" || s === "reject" || s === "rejected") {
        rejectCount++;
      } else if (s === "approved by pengawas" || s === "approve" || s === "approved") {
        approvedCount++;
      } else if (s === "kosong" || s === "") {
        emptyCount++;
      }
    });

    const otherCount = submitCount + rejectCount + approvedCount;
    const completionRate = total > 0 ? (otherCount / total) * 100 : 0;
    const activeOfficers = new Set(rawData.map(r => r.officer).filter(Boolean)).size;

    return {
      total,
      openCount,
      draftCount,
      submitCount,
      rejectCount,
      approvedCount,
      emptyCount,
      otherCount,
      completionRate,
      activeOfficers
    };
  }, [rawData]);

  // Derived display stats that fall back to dynamic rawData-based stats
  const { displayTotal, displayOpen, displaySubmit, displayApprove, displayDraft, displayReject, displayRealisasi, displayRealisasiFasih } = useMemo(() => {
    const dTotal = totalPrelistSummary || stats.total;
    const dOpen = summaryStatusCounts.open || stats.openCount;
    const dSubmit = summaryStatusCounts.submit || stats.submitCount;
    const dApprove = summaryStatusCounts.approve || stats.approvedCount;
    const dDraft = summaryStatusCounts.draft || stats.draftCount;
    const dReject = summaryStatusCounts.reject || stats.rejectCount;

    return {
      displayTotal: dTotal,
      displayOpen: dOpen,
      displaySubmit: dSubmit,
      displayApprove: dApprove,
      displayDraft: dDraft,
      displayReject: dReject,
      displayRealisasi: dDraft + dSubmit + dApprove + dReject,
      displayRealisasiFasih: dSubmit + dApprove + dReject
    };
  }, [totalPrelistSummary, summaryStatusCounts, stats]);

  // Unique filters data
  const filterOptions = useMemo(() => {
    const statuses = Array.from(new Set(rawData.map(r => r.status))).filter(Boolean);
    const scales = Array.from(new Set(rawData.map(r => r.scale))).filter(Boolean);
    const officers = Array.from(new Set(rawData.map(r => r.officer))).filter(Boolean).sort();
    const subdistricts = Array.from(new Set(rawData.map(r => r.nama_kec))).filter(Boolean).sort();
    const kosekas = Array.from(new Set(rawData.map(r => r.koseka))).filter(Boolean).sort();

    return {
      statuses,
      scales,
      officers,
      subdistricts,
      kosekas
    };
  }, [rawData]);

  // Officer leaderboard (Top 10)
  const officerLeaderboard = useMemo(() => {
    const counts: { [key: string]: { total: number; open: number; selesai: number } } = {};
    
    rawData.forEach(r => {
      if (!r.officer) return;
      if (!counts[r.officer]) {
        counts[r.officer] = { total: 0, open: 0, selesai: 0 };
      }
      counts[r.officer].total++;
      const s = r.status.toLowerCase().trim();
      if (s === "open" || s === "draft" || s === "kosong" || s === "") {
        counts[r.officer].open++;
      } else if (
        s === "submitted by pencacah" ||
        s === "rejected by pengawas" ||
        s === "approved by pengawas" ||
        s === "submit" ||
        s === "submitted" ||
        s === "reject" ||
        s === "rejected" ||
        s === "approve" ||
        s === "approved"
      ) {
        counts[r.officer].selesai++;
      }
    });

    return Object.entries(counts)
      .map(([name, data]) => ({ name, ...data }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 8);
  }, [rawData]);

  // Scale distribution data for visual charts
  const scaleDistribution = useMemo(() => {
    const counts: { [key: string]: number } = {};
    rawData.forEach(r => {
      const scale = r.scale || "TIDAK TERIDENTIFIKASI";
      counts[scale] = (counts[scale] || 0) + 1;
    });

    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [rawData]);

  // Kecamatan stats and ranking for realization percentage (derived from dashboardRawData)
  const kecamatanRealisasiStats = useMemo(() => {
    const map: {
      [kecName: string]: {
        namaKec: string;
        slsCount: number;
        open: number;
        draft: number;
        submit: number;
        reject: number;
        approve: number;
        total: number;
        progress: number;
        realisasi: number;
      };
    } = {};

    dashboardRawData.forEach(record => {
      if (record.category.toLowerCase() !== "pengawas") return;
      const kec = record.namaKec || "-";
      const email = record.email.toLowerCase().trim();
      if (!email) return;

      if (!map[kec]) {
        map[kec] = {
          namaKec: kec,
          slsCount: 0,
          open: 0,
          draft: 0,
          submit: 0,
          reject: 0,
          approve: 0,
          total: 0,
          progress: 0,
          realisasi: 0,
        };
      }

      const k = map[kec];
      const slsTotal = record.open + record.draft + record.submit + record.reject + record.approve;
      const slsProgress = record.draft + record.submit + record.reject + record.approve;

      k.open += record.open;
      k.draft += record.draft;
      k.submit += record.submit;
      k.reject += record.reject;
      k.approve += record.approve;
      k.total += slsTotal;
      k.progress += slsProgress;
      k.realisasi += slsProgress;
      k.slsCount += 1;
    });

    return Object.values(map)
      .map(k => {
        const pctRealisasi = k.total > 0 ? (k.realisasi / k.total) * 100 : 0;
        return {
          ...k,
          pctRealisasi,
        };
      })
      .sort((a, b) => b.pctRealisasi - a.pctRealisasi);
  }, [dashboardRawData]);

  // Filtered and Searched data
  const filteredData = useMemo(() => {
    return rawData.filter(r => {
      // Search filter (ID Code, Name, Address, Officer, or Notes)
      const matchesSearch = searchQuery
        ? r.idCode.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.address.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.officer.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.notes.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (r.nama_kec && r.nama_kec.toLowerCase().includes(searchQuery.toLowerCase())) ||
          (r.koseka && r.koseka.toLowerCase().includes(searchQuery.toLowerCase()))
        : true;

      // Status filter
      const matchesStatus = statusFilter === "all"
        ? true
        : r.status.toLowerCase() === statusFilter.toLowerCase();

      // Scale filter
      const matchesScale = scaleFilter === "all"
        ? true
        : r.scale.toLowerCase() === scaleFilter.toLowerCase();

      // Officer filter
      const matchesOfficer = selectedOfficer === "all"
        ? true
        : r.officer === selectedOfficer;

      // Kecamatan filter
      const matchesSubdistrict = selectedSubdistrict === "all"
        ? true
        : r.nama_kec === selectedSubdistrict;

      // Koseka filter
      const matchesKoseka = selectedKoseka === "all"
        ? true
        : r.koseka === selectedKoseka;

      return matchesSearch && matchesStatus && matchesScale && matchesOfficer && matchesSubdistrict && matchesKoseka;
    });
  }, [rawData, searchQuery, statusFilter, scaleFilter, selectedOfficer, selectedSubdistrict, selectedKoseka]);

  useEffect(() => {
    const updateWidth = () => {
      if (tableContainerRef.current) {
        const table = tableContainerRef.current.querySelector("table");
        if (table) {
          setTableWidth(table.offsetWidth);
        }
      }
    };

    updateWidth();
    const timer = setTimeout(updateWidth, 300);
    window.addEventListener("resize", updateWidth);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", updateWidth);
    };
  }, [rawData, filteredData, currentPage]);

  // Reset page number on filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, scaleFilter, selectedOfficer, selectedSubdistrict, selectedKoseka]);

  // Paginated data for display
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return filteredData.slice(startIndex, startIndex + pageSize);
  }, [filteredData, currentPage]);

  const totalPages = Math.ceil(filteredData.length / pageSize) || 1;

  // Helper to generate export CSV url
  const handleExportCSV = () => {
    const headers = [
      "Kode Identitas", "Nama Keluarga/Bangunan/Usaha", "Kecamatan", "Koseka", "Alamat Prelist", 
      "Skala Usaha", "Status", "Petugas Saat Ini", "Keterangan", "Prioritas"
    ];
    const csvRows = [headers.join(",")];
    
    filteredData.forEach(r => {
      const values = [
        `"${r.idCode.replace(/"/g, '""')}"`,
        `"${r.name.replace(/"/g, '""')}"`,
        `"${(r.nama_kec || "").replace(/"/g, '""')}"`,
        `"${(r.koseka || "").replace(/"/g, '""')}"`,
        `"${r.address.replace(/"/g, '""')}"`,
        `"${r.scale.replace(/"/g, '""')}"`,
        `"${r.status.replace(/"/g, '""')}"`,
        `"${r.officer.replace(/"/g, '""')}"`,
        `"${r.notes.replace(/"/g, '""')}"`,
        `"${(r.isPrioritas || "Tidak").replace(/"/g, '""')}"`
      ];
      csvRows.push(values.join(","));
    });

    const csvBlob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(csvBlob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `filtered_monitoring_se2026_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Status Badge Component
  const StatusBadge = ({ status }: { status: string }) => {
    const s = status.toLowerCase().trim();
    if (s === "open") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20">
          <Clock className="w-3.5 h-3.5" />
          Terbuka (Open)
        </span>
      );
    } else if (s === "draft") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-500 border border-blue-500/20">
          <FileText className="w-3.5 h-3.5" />
          Draft
        </span>
      );
    } else if (s === "submitted by pencacah" || s === "submit" || s === "submitted") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-teal-500/10 text-teal-500 border border-teal-500/20">
          <Send className="w-3.5 h-3.5" />
          Submitted by Pencacah
        </span>
      );
    } else if (s === "rejected by pengawas" || s === "reject" || s === "rejected") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/10 text-red-500 border border-red-500/20">
          <XCircle className="w-3.5 h-3.5" />
          Rejected by Pengawas
        </span>
      );
    } else if (s === "approved by pengawas" || s === "approve" || s === "approved") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Approved by Pengawas
        </span>
      );
    } else if (s === "kosong" || s === "") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
          <AlertCircle className="w-3.5 h-3.5" />
          Belum Diisi
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
          <AlertCircle className="w-3.5 h-3.5" />
          {status}
        </span>
      );
    }
  };

  // Scale Badge Component
  const ScaleBadge = ({ scale }: { scale: string }) => {
    const s = scale.toUpperCase();
    let colorClass = "bg-orange-500/10 text-orange-500 border border-orange-500/20";
    if (s.includes("KELUARGA")) {
      colorClass = "bg-blue-500/10 text-blue-400 border border-blue-500/20";
    } else if (s.includes("UMK")) {
      colorClass = "bg-orange-500/10 text-orange-400 border border-orange-500/20";
    } else if (s.includes("UMKM")) {
      colorClass = "bg-purple-500/10 text-purple-400 border border-purple-500/20";
    }
    
    return (
      <span className={`inline-flex px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider ${colorClass}`}>
        {scale}
      </span>
    );
  };

  return (
    <div className={`min-h-screen font-sans transition-colors duration-300 ${isDarkMode ? "dark bg-slate-950 text-slate-100" : "bg-slate-50 text-slate-900"}`}>
      
      {/* Header Bar */}
      <header className="sticky top-0 z-30 border-b backdrop-blur-md transition-colors bg-white/80 dark:bg-slate-900/80 border-slate-200 dark:border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Visual BPS Logo Icon */}
            <div className="w-10 h-10 flex items-center justify-center bg-white dark:bg-slate-800 rounded-xl p-1 shadow-md border border-slate-200 dark:border-slate-700">
              <img src="/icon.png" alt="Logo BPS" className="w-8 h-8 object-contain" />
            </div>
            <div>
              <h1 className="text-sm sm:text-base font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                BPS Kabupaten Kepulauan Sangihe
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Dashboard Monitoring Sensus Ekonomi 2026
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <nav className="flex items-center gap-1 border border-slate-200 dark:border-slate-800 rounded-xl p-1 bg-slate-50/50 dark:bg-slate-950/50">
              <a 
                href="/" 
                className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-orange-500 text-white shadow-sm"
              >
                Dashboard
              </a>
              <a 
                href="/tabulasi" 
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                Tabulasi
              </a>
              <a 
                href="/petugas" 
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              >
                Petugas
              </a>
            </nav>

            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
              title="Ganti Tema"
            >
              {isDarkMode ? <Sun className="w-4 h-4 text-orange-400" /> : <Moon className="w-4 h-4 text-slate-700" />}
            </button>
            <button
              onClick={fetchData}
              disabled={loading}
              className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors disabled:opacity-50"
              title="Segarkan Data"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-orange-500" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Banner Title */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-orange-600 to-amber-500 p-8 sm:p-10 text-white shadow-xl shadow-orange-600/10 mb-8">
          {/* Decorative shapes */}
          <div className="absolute right-0 top-0 w-80 h-80 rounded-full bg-white/10 blur-3xl translate-x-20 -translate-y-20"></div>
          <div className="absolute right-1/4 bottom-0 w-60 h-60 rounded-full bg-orange-400/20 blur-2xl translate-y-20"></div>
          
          <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div>
              <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-white/20 text-white mb-3 inline-block">
                Monitoring Real-time
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight mb-2">
                Dashboard Monitoring SE2026
              </h2>
              <p className="text-sm sm:text-lg text-orange-50 max-w-2xl font-light">
                Pantau progres pendataan petugas Sensus Ekonomi 2026 secara akurat di wilayah Kabupaten Kepulauan Sangihe.
              </p>
            </div>
            
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 self-start md:self-auto flex flex-col items-end border border-white/10 text-right">
              <span className="text-xs text-orange-200">Terakhir Diperbarui</span>
              <span className="text-base font-bold flex items-center gap-1.5 mt-0.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
                {loading ? "Menyinkronkan..." : lastUpdated || "Belum ada data"}
              </span>
            </div>
          </div>
        </div>

        {/* Loading and Error States */}
        {loading && rawData.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="relative w-16 h-16">
              <div className="absolute top-0 left-0 w-full h-full rounded-full border-4 border-slate-200 dark:border-slate-800"></div>
              <div className="absolute top-0 left-0 w-full h-full rounded-full border-4 border-orange-500 border-t-transparent animate-spin"></div>
            </div>
            <p className="text-slate-500 dark:text-slate-400 font-medium animate-pulse text-sm">
              Mengekstrak dan Memproses Data CSV BPS FASIH...
            </p>
          </div>
        ) : error ? (
          <div className="p-6 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-500 text-center mb-8">
            <AlertCircle className="w-10 h-10 mx-auto mb-3" />
            <h3 className="font-bold text-lg mb-1">Terjadi Kesalahan</h3>
            <p className="text-sm opacity-90 max-w-md mx-auto mb-4">{error}</p>
            <button
              onClick={fetchData}
              className="px-4 py-2 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-colors text-sm font-semibold"
            >
              Coba Lagi
            </button>
          </div>
        ) : (
          <>
            {/* Stats Overview */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 gap-5 mb-8">
              
              {/* Total Target Prelist */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300"
              >
                <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Total Target Prelist</span>
                <span className="text-3xl font-extrabold mt-2 block text-slate-900 dark:text-white">
                  {displayTotal.toLocaleString("id-ID")}
                </span>
                <span className="text-xs text-slate-400 mt-2 block flex items-center gap-1">
                  <FileSpreadsheet className="w-3.5 h-3.5 text-orange-500" />
                  {totalPrelistSummary ? "Target resmi dari BPS FASIH" : "Baris data valid terkumpul"}
                </span>
              </motion.div>

              {/* Total Realisasi */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.03 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300 flex flex-col justify-between"
              >
                <div>
                  <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Total Realisasi</span>
                  <span className="text-3xl font-extrabold mt-2 block text-emerald-500">
                    {displayRealisasi.toLocaleString("id-ID")}
                  </span>
                </div>
                <div>
                  <div className="flex items-center justify-between mt-3 gap-2">
                    <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${displayTotal > 0 ? (displayRealisasi / displayTotal) * 100 : 0}%` }}></div>
                    </div>
                    <span className="text-xs sm:text-sm font-extrabold text-slate-700 dark:text-slate-200 whitespace-nowrap">{displayTotal > 0 ? ((displayRealisasi / displayTotal) * 100).toFixed(2) : "0.00"}%</span>
                  </div>
                  <span className="text-[9px] text-slate-400 dark:text-slate-500 mt-2 block font-medium leading-tight">
                    * Selain status Open (Draft + Submit + Approve + Reject)
                  </span>
                </div>
              </motion.div>

              {/* Realisasi via Fasih SM */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.06 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300 flex flex-col justify-between"
              >
                <div>
                  <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Realisasi via Fasih SM</span>
                  <span className="text-3xl font-extrabold mt-2 block text-teal-500">
                    {displayRealisasiFasih.toLocaleString("id-ID")}
                  </span>
                </div>
                <div>
                  <div className="flex items-center justify-between mt-3 gap-2">
                    <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div className="bg-teal-500 h-full rounded-full" style={{ width: `${displayTotal > 0 ? (displayRealisasiFasih / displayTotal) * 100 : 0}%` }}></div>
                    </div>
                    <span className="text-xs sm:text-sm font-extrabold text-slate-700 dark:text-slate-200 whitespace-nowrap">{displayTotal > 0 ? ((displayRealisasiFasih / displayTotal) * 100).toFixed(2) : "0.00"}%</span>
                  </div>
                  <span className="text-[9px] text-slate-400 dark:text-slate-500 mt-2 block font-medium leading-tight">
                    * Selain Open & Draft (Submit + Approve + Reject)
                  </span>
                </div>
              </motion.div>

              {/* Status Terbuka (Open) */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.09 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300"
              >
                <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Status Terbuka (Open)</span>
                <span className="text-3xl font-extrabold mt-2 block text-amber-500">
                  {displayOpen.toLocaleString("id-ID")}
                </span>
                <div className="flex items-center justify-between mt-3 gap-2">
                  <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className="bg-amber-500 h-full rounded-full" style={{ width: `${displayTotal > 0 ? (displayOpen / displayTotal) * 100 : 0}%` }}></div>
                  </div>
                  <span className="text-xs sm:text-sm font-extrabold text-slate-700 dark:text-slate-200 whitespace-nowrap">{displayTotal > 0 ? ((displayOpen / displayTotal) * 100).toFixed(2) : "0.00"}%</span>
                </div>
              </motion.div>

              {/* Status Submitted by Pencacah */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.12 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300"
              >
                <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Submitted by Pencacah</span>
                <span className="text-3xl font-extrabold mt-2 block text-teal-500">
                  {displaySubmit.toLocaleString("id-ID")}
                </span>
                <div className="flex items-center justify-between mt-3 gap-2">
                  <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className="bg-teal-500 h-full rounded-full" style={{ width: `${displayTotal > 0 ? (displaySubmit / displayTotal) * 100 : 0}%` }}></div>
                  </div>
                  <span className="text-xs sm:text-sm font-extrabold text-slate-700 dark:text-slate-200 whitespace-nowrap">{displayTotal > 0 ? ((displaySubmit / displayTotal) * 100).toFixed(2) : "0.00"}%</span>
                </div>
              </motion.div>

              {/* Status Approved by Pengawas */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.15 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300"
              >
                <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Approved by Pengawas</span>
                <span className="text-3xl font-extrabold mt-2 block text-emerald-500">
                  {displayApprove.toLocaleString("id-ID")}
                </span>
                <div className="flex items-center justify-between mt-3 gap-2">
                  <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${displayTotal > 0 ? (displayApprove / displayTotal) * 100 : 0}%` }}></div>
                  </div>
                  <span className="text-xs sm:text-sm font-extrabold text-slate-700 dark:text-slate-200 whitespace-nowrap">{displayTotal > 0 ? ((displayApprove / displayTotal) * 100).toFixed(2) : "0.00"}%</span>
                </div>
              </motion.div>

              {/* Status Draft */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.18 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300"
              >
                <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Status Draft</span>
                <span className="text-3xl font-extrabold mt-2 block text-blue-500">
                  {displayDraft.toLocaleString("id-ID")}
                </span>
                <div className="flex items-center justify-between mt-3 gap-2">
                  <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className="bg-blue-500 h-full rounded-full" style={{ width: `${displayTotal > 0 ? (displayDraft / displayTotal) * 100 : 0}%` }}></div>
                  </div>
                  <span className="text-xs sm:text-sm font-extrabold text-slate-700 dark:text-slate-200 whitespace-nowrap">{displayTotal > 0 ? ((displayDraft / displayTotal) * 100).toFixed(2) : "0.00"}%</span>
                </div>
              </motion.div>

              {/* Status Rejected by Pengawas */}
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.21 }}
                className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300"
              >
                <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800/40 group-hover:bg-orange-500/5 transition-colors duration-300"></div>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold block uppercase tracking-wider">Rejected by Pengawas</span>
                <span className="text-3xl font-extrabold mt-2 block text-red-500">
                  {displayReject.toLocaleString("id-ID")}
                </span>
                <div className="flex items-center justify-between mt-3 gap-2">
                  <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div className="bg-red-500 h-full rounded-full" style={{ width: `${displayTotal > 0 ? (displayReject / displayTotal) * 100 : 0}%` }}></div>
                  </div>
                  <span className="text-xs sm:text-sm font-extrabold text-slate-700 dark:text-slate-200 whitespace-nowrap">{displayTotal > 0 ? ((displayReject / displayTotal) * 100).toFixed(2) : "0.00"}%</span>
                </div>
              </motion.div>

            </div>

            {/* Kecamatan Realization Ranking Card */}
            <div className="mb-8 animate-fade-in">
              <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm hover:border-orange-500/30 transition-all duration-300">
                <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <div className="p-2.5 rounded-xl bg-orange-500/10 text-orange-500">
                      <TrendingUp className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-base sm:text-lg text-slate-900 dark:text-white">Peringkat Realisasi Kecamatan</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Distribusi persentase realisasi target prelist per Kecamatan (Draft + Submit + Approve + Reject)</p>
                    </div>
                  </div>
                  <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 px-2.5 py-1 rounded-lg font-bold">
                    Diurutkan dari Tertinggi
                  </span>
                </div>

                {loading && dashboardRawData.length === 0 ? (
                  <div className="flex justify-center py-6 text-slate-400 text-xs">Memuat rekapitulasi kecamatan...</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
                    {kecamatanRealisasiStats.map((item, idx) => {
                      const pct = item.pctRealisasi;
                      
                      let colorClass = "from-orange-500 to-amber-500";
                      let bgClass = "bg-orange-500/10";
                      let textClass = "text-orange-500";
                      
                      if (pct >= 80) {
                        colorClass = "from-emerald-500 to-teal-500";
                        bgClass = "bg-emerald-500/10";
                        textClass = "text-emerald-500";
                      } else if (pct >= 40) {
                        colorClass = "from-blue-600 to-cyan-500";
                        bgClass = "bg-blue-500/10";
                        textClass = "text-blue-500";
                      }

                      return (
                        <div key={item.namaKec} className="flex flex-col gap-1.5 p-3 rounded-2xl hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                          <div className="flex justify-between items-center text-xs font-semibold">
                            <span className="flex items-center gap-2">
                              <span className={`w-5 h-5 flex items-center justify-center rounded-lg text-[10px] font-bold ${
                                idx === 0 
                                  ? "bg-amber-500 text-white" 
                                  : idx === 1 
                                  ? "bg-slate-300 text-slate-800" 
                                  : idx === 2 
                                  ? "bg-amber-700 text-white" 
                                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                              }`}>
                                {idx + 1}
                              </span>
                              <span className="uppercase tracking-wider text-slate-700 dark:text-slate-300 truncate max-w-[150px]">
                                {formatKecName(item.namaKec)}
                              </span>
                            </span>
                            <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                              <span className="text-[10px] text-slate-400 dark:text-slate-500 font-normal">
                                {item.realisasi.toLocaleString("id-ID")} / {item.total.toLocaleString("id-ID")}
                              </span>
                              <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${bgClass} ${textClass}`}>
                                {pct.toFixed(2)}%
                              </span>
                            </span>
                          </div>
                          <div className="h-3 bg-slate-100 dark:bg-slate-800/50 rounded-full overflow-hidden flex shadow-inner">
                            <div
                              className={`bg-gradient-to-r ${colorClass} h-full rounded-full transition-all duration-500`}
                              style={{ width: `${pct}%` }}
                            ></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Bento Section: Distribution Chart */}
            <div className="mb-8">
              {/* Distribusi Skala Usaha */}
              <div className="bg-white dark:bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <div className="flex items-center gap-2 mb-6">
                  <div className="p-2.5 rounded-xl bg-orange-500/10 text-orange-500">
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base sm:text-lg text-slate-900 dark:text-white">Distribusi Jenis Prelist / Skala</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Pembagian sampel berdasarkan skala usaha (Bar Chart)</p>
                  </div>
                </div>

                <div className="space-y-5">
                  {scaleDistribution.map((item, idx) => {
                    const total = stats.total || 1;
                    const pct = (item.value / total) * 100;
                    
                    let colorClass = "from-orange-500 to-amber-500";
                    let bgClass = "bg-orange-500/10";
                    let textClass = "text-orange-500";
                    
                    if (item.name.toUpperCase().includes("KELUARGA")) {
                      colorClass = "from-blue-600 to-cyan-500";
                      bgClass = "bg-blue-500/10";
                      textClass = "text-blue-500";
                    } else if (item.name.toUpperCase().includes("UMK")) {
                      colorClass = "from-orange-500 to-amber-500";
                      bgClass = "bg-orange-500/10";
                      textClass = "text-orange-500";
                    } else if (item.name.toUpperCase().includes("UMKM")) {
                      colorClass = "from-purple-600 to-pink-500";
                      bgClass = "bg-purple-500/10";
                      textClass = "text-purple-500";
                    }

                    return (
                      <div key={idx} className="space-y-2">
                        <div className="flex justify-between items-center text-xs sm:text-sm font-semibold">
                          <span className="uppercase tracking-wider text-slate-700 dark:text-slate-300">
                            {item.name}
                          </span>
                          <span className="font-bold text-slate-900 dark:text-white">
                            {item.value.toLocaleString("id-ID")}{" "}
                            <span className="font-extrabold text-xs sm:text-sm text-slate-700 dark:text-slate-200 ml-1">
                              ({pct.toFixed(2)}%)
                            </span>
                          </span>
                        </div>
                        <div className="h-4 bg-slate-100 dark:bg-slate-800/50 rounded-full overflow-hidden flex shadow-inner">
                          <div
                            className={`bg-gradient-to-r ${colorClass} h-full rounded-full transition-all duration-500`}
                            style={{ width: `${pct}%` }}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Filter and Table Card */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
              
              {/* Filter Section */}
              <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                  
                  {/* Search input */}
                  <div className="relative w-full md:max-w-md">
                    <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Cari nama, ID prelist, alamat, atau petugas..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 text-sm transition-all"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery("")}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  {/* Actions / Export Button */}
                  <div className="w-full md:w-auto flex items-center justify-end">
                    <button
                      onClick={handleExportCSV}
                      className="w-full md:w-auto px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors flex items-center justify-center gap-2 text-sm font-semibold bg-white dark:bg-slate-950 cursor-pointer"
                      title="Ekspor CSV Hasil Filter"
                    >
                      <Download className="w-4 h-4 text-orange-500" />
                      <span>Ekspor Data</span>
                    </button>
                  </div>

                </div>

                {/* Dropdowns Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mt-4">
                  
                  {/* Filter Status */}
                  <div className="relative w-full">
                    <Clock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      className="w-full pl-10 pr-9 py-2.5 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 text-xs font-semibold appearance-none cursor-pointer"
                    >
                      <option value="all">Semua Status</option>
                      {filterOptions.statuses.map((s, idx) => {
                        let label = s;
                        if (s.toLowerCase() === "open") label = "Terbuka (Open)";
                        else if (s.toLowerCase() === "draft") label = "Draft";
                        else if (s.toLowerCase() === "submitted by pencacah") label = "Submitted by Pencacah";
                        else if (s.toLowerCase() === "rejected by pengawas") label = "Rejected by Pengawas";
                        else if (s.toLowerCase() === "approved by pengawas") label = "Approved by Pengawas";
                        return (
                          <option key={idx} value={s}>{label}</option>
                        );
                      })}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>

                  {/* Filter Kecamatan */}
                  <div className="relative w-full">
                    <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <select
                      value={selectedSubdistrict}
                      onChange={(e) => setSelectedSubdistrict(e.target.value)}
                      className="w-full pl-10 pr-9 py-2.5 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 text-xs font-semibold appearance-none cursor-pointer"
                    >
                      <option value="all">Semua Kecamatan</option>
                      {filterOptions.subdistricts.map((sub, idx) => (
                        <option key={idx} value={sub}>{sub}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>

                  {/* Filter Koseka */}
                  <div className="relative w-full">
                    <Building className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <select
                      value={selectedKoseka}
                      onChange={(e) => setSelectedKoseka(e.target.value)}
                      className="w-full pl-10 pr-9 py-2.5 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 text-xs font-semibold appearance-none cursor-pointer"
                    >
                      <option value="all">Semua Koseka</option>
                      {filterOptions.kosekas.map((kos, idx) => (
                        <option key={idx} value={kos}>{kos}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>

                  {/* Filter Skala */}
                  <div className="relative w-full">
                    <Layers className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <select
                      value={scaleFilter}
                      onChange={(e) => setScaleFilter(e.target.value)}
                      className="w-full pl-10 pr-9 py-2.5 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 text-xs font-semibold appearance-none cursor-pointer"
                    >
                      <option value="all">Semua Skala</option>
                      {filterOptions.scales.map((sc, idx) => (
                        <option key={idx} value={sc}>{sc}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>

                  {/* Filter Petugas */}
                  <div className="relative w-full">
                    <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <select
                      value={selectedOfficer}
                      onChange={(e) => setSelectedOfficer(e.target.value)}
                      className="w-full pl-10 pr-9 py-2.5 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 text-xs font-semibold appearance-none cursor-pointer"
                    >
                      <option value="all">Semua Petugas</option>
                      {filterOptions.officers.map((off, idx) => (
                        <option key={idx} value={off}>{off.replace(/Pencacah$/, "")}</option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>

                </div>

                {/* Filter Summary Badge */}
                {(searchQuery || statusFilter !== "all" || scaleFilter !== "all" || selectedOfficer !== "all" || selectedSubdistrict !== "all" || selectedKoseka !== "all") && (
                  <div className="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-slate-200/50 dark:border-slate-800/50 text-xs">
                    <span className="text-slate-400 font-medium">Filter Aktif:</span>
                    {searchQuery && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-orange-500/10 text-orange-500 font-medium">
                        Cari: "{searchQuery}"
                        <button onClick={() => setSearchQuery("")}><X className="w-3 h-3 hover:text-orange-600" /></button>
                      </span>
                    )}
                    {statusFilter !== "all" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-orange-500/10 text-orange-500 font-medium">
                        Status: {statusFilter}
                        <button onClick={() => setStatusFilter("all")}><X className="w-3 h-3 hover:text-orange-600" /></button>
                      </span>
                    )}
                    {scaleFilter !== "all" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-orange-500/10 text-orange-500 font-medium">
                        Skala: {scaleFilter}
                        <button onClick={() => setScaleFilter("all")}><X className="w-3 h-3 hover:text-orange-600" /></button>
                      </span>
                    )}
                    {selectedOfficer !== "all" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-orange-500/10 text-orange-500 font-medium">
                        Petugas: {selectedOfficer.replace(/Pencacah$/, "")}
                        <button onClick={() => setSelectedOfficer("all")}><X className="w-3 h-3 hover:text-orange-600" /></button>
                      </span>
                    )}
                    {selectedSubdistrict !== "all" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-orange-500/10 text-orange-500 font-medium">
                        Kecamatan: {selectedSubdistrict}
                        <button onClick={() => setSelectedSubdistrict("all")}><X className="w-3 h-3 hover:text-orange-600" /></button>
                      </span>
                    )}
                    {selectedKoseka !== "all" && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-orange-500/10 text-orange-500 font-medium">
                        Koseka: {selectedKoseka}
                        <button onClick={() => setSelectedKoseka("all")}><X className="w-3 h-3 hover:text-orange-600" /></button>
                      </span>
                    )}
                    <button
                      onClick={() => {
                        setSearchQuery("");
                        setStatusFilter("all");
                        setScaleFilter("all");
                        setSelectedOfficer("all");
                        setSelectedSubdistrict("all");
                        setSelectedKoseka("all");
                      }}
                      className="text-slate-400 hover:text-orange-500 hover:underline font-bold ml-auto"
                    >
                      Bersihkan Semua
                    </button>
                  </div>
                )}
              </div>

              {/* Top scrollbar synced with table */}
              <div 
                ref={topScrollRef}
                onScroll={handleTopScroll}
                className="overflow-x-auto overflow-y-hidden w-full bg-slate-50/30 dark:bg-slate-900/30 border-b border-slate-200 dark:border-slate-800"
                style={{ height: "10px" }}
              >
                <div style={{ width: `${tableWidth}px`, height: "10px" }} />
              </div>

              {/* Data Table */}
              <div 
                ref={tableContainerRef}
                onScroll={handleTableScroll}
                className="overflow-auto max-h-[650px] w-full"
              >
                <table className="w-full text-left border-collapse">
                  <thead className="sticky top-0 z-20 bg-slate-50 dark:bg-slate-900 shadow-[0_1px_0_0_rgba(226,232,240,1)] dark:shadow-[0_1px_0_0_rgba(30,41,59,1)]">
                    <tr className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Kode Identitas</th>
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Nama Keluarga/Bangunan/Usaha</th>
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Kecamatan</th>
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Koseka</th>
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Alamat Prelist</th>
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Skala Prelist</th>
                      <th className="py-4 px-6 text-center bg-slate-50 dark:bg-slate-900">Status</th>
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Petugas</th>
                      <th className="py-4 px-6 bg-slate-50 dark:bg-slate-900">Keterangan</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800/50 text-sm">
                    {paginatedData.length > 0 ? (
                      paginatedData.map((row, idx) => (
                        <tr
                          key={idx}
                          className={`hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-all border-l-2 ${
                            row.isPrioritas === "Ya"
                              ? "bg-orange-500/5 hover:bg-orange-500/10 dark:bg-orange-500/5 dark:hover:bg-orange-500/10 border-l-orange-500"
                              : "border-l-transparent"
                          }`}
                        >
                          {/* ID Code */}
                          <td className="py-4 px-6 font-mono text-xs font-semibold text-slate-800 dark:text-slate-300 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <span>{row.idCode}</span>
                              {row.isPrioritas === "Ya" && (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase bg-orange-500/15 text-orange-600 dark:text-orange-400 border border-orange-500/30 tracking-wider shadow-sm animate-pulse">
                                  Prioritas
                                </span>
                              )}
                            </div>
                          </td>
                          {/* Name */}
                          <td className="py-4 px-6 font-medium text-slate-900 dark:text-white truncate max-w-[180px]">
                            {row.name || "-"}
                          </td>
                          {/* Kecamatan */}
                          <td className="py-4 px-6 text-slate-500 dark:text-slate-400 truncate max-w-[150px]">
                            {row.nama_kec || "-"}
                          </td>
                          {/* Koseka */}
                          <td className="py-4 px-6 text-slate-500 dark:text-slate-400 font-semibold whitespace-nowrap">
                            {row.koseka || "-"}
                          </td>
                          {/* Address */}
                          <td className="py-4 px-6 text-slate-500 dark:text-slate-400 truncate max-w-[180px]">
                            {row.address || "-"}
                          </td>
                          {/* Scale */}
                          <td className="py-4 px-6">
                            <ScaleBadge scale={row.scale} />
                          </td>
                          {/* Status */}
                          <td className="py-4 px-6 text-center whitespace-nowrap">
                            <StatusBadge status={row.status} />
                          </td>
                          {/* Officer */}
                          <td className="py-4 px-6 text-slate-600 dark:text-slate-400 font-medium truncate max-w-[150px]">
                            {row.officer ? row.officer.replace(/Pencacah$/, "") : "-"}
                          </td>
                          {/* Notes */}
                          <td className="py-4 px-6 text-xs text-slate-400 truncate max-w-[120px]">
                            {row.notes || "-"}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={9} className="py-12 px-6 text-center text-slate-500 dark:text-slate-400">
                          Tidak ditemukan data yang cocok dengan kriteria pencarian dan filter Anda.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Table Footer / Pagination */}
              <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex flex-col sm:flex-row items-center justify-between gap-4">
                
                {/* Stats */}
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  Menampilkan <span className="font-bold text-slate-900 dark:text-white">
                    {Math.min(filteredData.length, (currentPage - 1) * pageSize + 1)}-{Math.min(filteredData.length, currentPage * pageSize)}
                  </span> dari <span className="font-bold text-slate-900 dark:text-white">
                    {filteredData.length.toLocaleString("id-ID")}
                  </span> data (Filter aktif dari total {stats.total.toLocaleString("id-ID")} prelist)
                </div>

                {/* Pagination Controls */}
                <div className="flex items-center gap-1">
                  
                  {/* Prev */}
                  <button
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    className="p-2 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 text-slate-500 cursor-pointer"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>

                  {/* Page Numbers display */}
                  <div className="hidden sm:flex items-center gap-1 text-xs">
                    {currentPage > 3 && (
                      <>
                        <button onClick={() => setCurrentPage(1)} className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800">1</button>
                        {currentPage > 4 && <span className="text-slate-400 px-1">...</span>}
                      </>
                    )}

                    {Array.from({ length: 5 }, (_, i) => {
                      const pageNum = currentPage - 2 + i;
                      if (pageNum > 0 && pageNum <= totalPages) {
                        const active = pageNum === currentPage;
                        return (
                          <button
                            key={pageNum}
                            onClick={() => setCurrentPage(pageNum)}
                            className={`px-3 py-1.5 rounded-lg border font-semibold transition-colors cursor-pointer ${
                              active
                                ? "bg-orange-500 border-orange-500 text-white shadow-md shadow-orange-500/10"
                                : "border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
                            }`}
                          >
                            {pageNum}
                          </button>
                        );
                      }
                      return null;
                    })}

                    {currentPage < totalPages - 2 && (
                      <>
                        {currentPage < totalPages - 3 && <span className="text-slate-400 px-1">...</span>}
                        <button onClick={() => setCurrentPage(totalPages)} className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800">{totalPages}</button>
                      </>
                    )}
                  </div>

                  {/* Simple mobile page number */}
                  <div className="flex sm:hidden px-2 text-xs font-semibold">
                    Halaman {currentPage} dari {totalPages}
                  </div>

                  {/* Next */}
                  <button
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                    className="p-2 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 text-slate-500 cursor-pointer"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>

                </div>

              </div>

            </div>
          </>
        )}

      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 dark:border-slate-800 py-6 text-center text-xs text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-900 transition-colors">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>&copy; 2026 Badan Pusat Statistik Kabupaten Kepulauan Sangihe. Hak Cipta Dilindungi.</span>
          <div className="flex items-center gap-3">
            <span className="font-semibold text-orange-500 flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" />
              Monitoring Sensus Ekonomi 2026
            </span>
            <span className="text-slate-300 dark:text-slate-700">|</span>
            <span>
              Pengembang:{" "}
              <a
                href="http://hamdani-portfolio.vercel.app/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-bold text-orange-500 hover:text-orange-600 dark:hover:text-orange-400 transition-colors"
              >
                Hamdani
              </a>
            </span>
          </div>
        </div>
      </footer>

    </div>
  );
}
