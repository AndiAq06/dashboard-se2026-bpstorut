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
  Moon,
  Sun,
  Download,
  RefreshCw,
  FileSpreadsheet,
  ChevronDown,
  ChevronRight,
  Filter,
  Send,
  XCircle,
  UserCheck,
  Percent,
  Layers,
  TrendingUp
} from "lucide-react";

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
  isPrioritas: string;    // Priority SLS flag
}

// Interface for aggregated officer stats
interface OfficerStats {
  namaPetugas: string;
  email: string;
  category: string;
  jabatanPetugas: string;
  namaKec: string;
  koseka: string;
  slsList: {
    slsCode: string;
    open: number;
    draft: number;
    submit: number;
    reject: number;
    approve: number;
    total: number;
    progress: number;
    isPrioritas: boolean;
  }[];
  open: number;
  draft: number;
  submit: number;
  reject: number;
  approve: number;
  total: number;
  progress: number; // sum of draft + submit + reject + approve
  realisasi: number; // sum of draft + submit + reject + approve
}

// Interface for aggregated kecamatan stats (grouped PML data)
interface KecamatanStats {
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
  pmlList: {
    namaPetugas: string;
    email: string;
    slsCount: number;
    open: number;
    draft: number;
    submit: number;
    reject: number;
    approve: number;
    total: number;
    progress: number;
    realisasi: number;
  }[];
}

export default function PetugasPage() {
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [rawData, setRawData] = useState<DashboardRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  // Tabs and filters state
  const [activeTab, setActiveTab] = useState<"pcl" | "pml" | "kecamatan" | "prioritas">("pcl");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedKec, setSelectedKec] = useState("all");
  const [sortBy, setSortBy] = useState<"nama" | "realisasi_desc" | "realisasi_asc" | "pct_desc" | "pct_asc">("nama");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  // Fetch and parse the CSV
  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch("/dashboard_scraped_data.csv");
      if (!response.ok) {
        throw new Error("Gagal mengambil data dashboard_scraped_data.csv. Jalankan pipeline data telebih dahulu.");
      }

      const text = await response.text();
      const parsed = parseCSV(text);
      setRawData(parsed);

      // Fetch last updated timestamp
      try {
        const timeResponse = await fetch("/last_updated.txt");
        if (timeResponse.ok) {
          const loadedTimestamp = (await timeResponse.text()).trim();
          setLastUpdated(loadedTimestamp);
        }
      } catch (e) {
        console.warn("Gagal memuat file last_updated.txt, fallback ke waktu sekarang.");
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

  // Simple Quote-Aware CSV Parser
  const parseCSV = (csvText: string): DashboardRecord[] => {
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

      // Ensure row has the required elements
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
          isPrioritas: row[12] ? row[12].replace(/"/g, "").trim() : "Tidak",
        });
      }
    }
    return parsed;
  };

  // Helper to format subdistrict names to Title Case and strip BPS codes
  const formatKecName = (name: string): string => {
    if (!name) return "-";
    let cleaned = name.replace(/\(\d+\)/g, "").trim();
    return cleaned
      .toLowerCase()
      .split(" ")
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  // Aggregate stats by officer
  const aggregatedStats = useMemo(() => {
    const map: { [email: string]: OfficerStats } = {};

    rawData.forEach(record => {
      const email = record.email.toLowerCase().trim();
      if (!email) return;

      if (!map[email]) {
        map[email] = {
          namaPetugas: record.namaPetugas || email.split("@")[0],
          email: record.email,
          category: record.category,
          jabatanPetugas: record.jabatanPetugas || (record.category === "Pengawas" ? "PML" : "PPL"),
          namaKec: record.namaKec,
          koseka: record.koseka || "-",
          slsList: [],
          open: 0,
          draft: 0,
          submit: 0,
          reject: 0,
          approve: 0,
          total: 0,
          progress: 0,
          realisasi: 0
        };
      }

      // Add SLS info
      const slsTotal = record.open + record.draft + record.submit + record.reject + record.approve;
      const slsProgress = record.draft + record.submit + record.reject + record.approve;

      map[email].slsList.push({
        slsCode: record.slsCode,
        open: record.open,
        draft: record.draft,
        submit: record.submit,
        reject: record.reject,
        approve: record.approve,
        total: slsTotal,
        progress: slsProgress,
        isPrioritas: record.isPrioritas === "Ya"
      });

      // Sum metrics
      map[email].open += record.open;
      map[email].draft += record.draft;
      map[email].submit += record.submit;
      map[email].reject += record.reject;
      map[email].approve += record.approve;
      map[email].total += slsTotal;
      map[email].progress += slsProgress;
      map[email].realisasi += slsProgress; // Realisasi = progres (jumlah status bukan open)
    });

    return Object.values(map);
  }, [rawData]);

  // Aggregate stats by kecamatan (summing PML data)
  const kecamatanStats = useMemo(() => {
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
        pmlMap: {
          [email: string]: {
            namaPetugas: string;
            email: string;
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
        };
      };
    } = {};

    rawData.forEach(record => {
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
          pmlMap: {}
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

      if (!k.pmlMap[email]) {
        k.pmlMap[email] = {
          namaPetugas: record.namaPetugas || email.split("@")[0],
          email: record.email,
          slsCount: 0,
          open: 0,
          draft: 0,
          submit: 0,
          reject: 0,
          approve: 0,
          total: 0,
          progress: 0,
          realisasi: 0
        };
      }
      const p = k.pmlMap[email];
      p.open += record.open;
      p.draft += record.draft;
      p.submit += record.submit;
      p.reject += record.reject;
      p.approve += record.approve;
      p.total += slsTotal;
      p.slsCount += 1;
      p.progress += slsProgress;
      p.realisasi += slsProgress;
    });

    return Object.values(map).map(k => {
      const { pmlMap, ...rest } = k;
      return {
        ...rest,
        pmlList: Object.values(pmlMap)
      };
    });
  }, [rawData]);

  // Unique Kecamatan List for filters
  const subdistrictOptions = useMemo(() => {
    const list = rawData.map(r => r.namaKec).filter(Boolean);
    return Array.from(new Set(list)).sort();
  }, [rawData]);

  // Aggregate stats for SLS Prioritas
  const prioritySLSStats = useMemo(() => {
    const map: { [slsCode: string]: {
      slsCode: string;
      namaKec: string;
      koseka: string;
      pencacah: string;
      pengawas: string;
      open: number;
      draft: number;
      submit: number;
      reject: number;
      approve: number;
      total: number;
      progress: number;
      realisasi: number;
      hasPengawasRecord: boolean;
    } } = {};

    rawData.forEach(record => {
      if (record.isPrioritas !== "Ya") return;
      const code = record.slsCode;
      
      if (!map[code]) {
        map[code] = {
          slsCode: code,
          namaKec: record.namaKec || "-",
          koseka: record.koseka || "-",
          pencacah: "-",
          pengawas: "-",
          open: 0,
          draft: 0,
          submit: 0,
          reject: 0,
          approve: 0,
          total: 0,
          progress: 0,
          realisasi: 0,
          hasPengawasRecord: false,
        };
      }

      const entry = map[code];

      // Collect officer names based on category
      const isPencacah = record.category.toLowerCase() === "pencacah";
      const isPengawas = record.category.toLowerCase() === "pengawas";

      if (isPencacah) {
        entry.pencacah = record.namaPetugas || "-";
      } else if (isPengawas) {
        entry.pengawas = record.namaPetugas || "-";
      }

      // If we don't have a Pengawas record yet, or this record IS the Pengawas record,
      // update the status counts.
      if (isPengawas || (!entry.hasPengawasRecord)) {
        entry.open = record.open;
        entry.draft = record.draft;
        entry.submit = record.submit;
        entry.reject = record.reject;
        entry.approve = record.approve;
        
        const slsTotal = record.open + record.draft + record.submit + record.reject + record.approve;
        const slsProgress = record.draft + record.submit + record.reject + record.approve;
        
        entry.total = slsTotal;
        entry.progress = slsProgress;
        entry.realisasi = slsProgress;

        if (isPengawas) {
          entry.hasPengawasRecord = true;
        }
      }

      // Ensure we fill in Kecamatan and Koseka if not already populated
      if (record.namaKec && entry.namaKec === "-") {
        entry.namaKec = record.namaKec;
      }
      if (record.koseka && entry.koseka === "-") {
        entry.koseka = record.koseka;
      }
    });

    return Object.values(map);
  }, [rawData]);

  // Filtered priority SLS list
  const filteredPrioritySLS = useMemo(() => {
    if (activeTab !== "prioritas") return [];

    const base = prioritySLSStats.filter(item => {
      // Subdistrict filter
      if (selectedKec !== "all" && item.namaKec !== selectedKec) {
        return false;
      }

      // Search query filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          item.slsCode.toLowerCase().includes(query) ||
          item.namaKec.toLowerCase().includes(query) ||
          item.koseka.toLowerCase().includes(query) ||
          item.pencacah.toLowerCase().includes(query) ||
          item.pengawas.toLowerCase().includes(query)
        );
      }

      return true;
    });

    // Sorting
    if (sortBy === "nama") {
      return base.sort((a, b) => a.slsCode.localeCompare(b.slsCode));
    } else if (sortBy === "realisasi_desc") {
      return base.sort((a, b) => b.realisasi - a.realisasi);
    } else if (sortBy === "realisasi_asc") {
      return base.sort((a, b) => a.realisasi - b.realisasi);
    } else if (sortBy === "pct_desc") {
      return base.sort((a, b) => {
        const pctA = a.total > 0 ? (a.realisasi / a.total) : 0;
        const pctB = b.total > 0 ? (b.realisasi / b.total) : 0;
        return pctB - pctA;
      });
    } else if (sortBy === "pct_asc") {
      return base.sort((a, b) => {
        const pctA = a.total > 0 ? (a.realisasi / a.total) : 0;
        const pctB = b.total > 0 ? (b.realisasi / b.total) : 0;
        return pctA - pctB;
      });
    }

    return base;
  }, [prioritySLSStats, activeTab, selectedKec, searchQuery, sortBy]);

  // Filtered officers list
  const filteredOfficers = useMemo(() => {
    const base = aggregatedStats.filter(off => {
      // Category filter (Tab: PCL or PML)
      const targetCategory = activeTab === "pcl" ? "Pencacah" : "Pengawas";
      if (off.category.toLowerCase() !== targetCategory.toLowerCase()) {
        return false;
      }

      // Subdistrict filter
      if (selectedKec !== "all" && off.namaKec !== selectedKec) {
        return false;
      }

      // Search query filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          off.namaPetugas.toLowerCase().includes(query) ||
          off.email.toLowerCase().includes(query) ||
          off.namaKec.toLowerCase().includes(query) ||
          off.koseka.toLowerCase().includes(query)
        );
      }

      return true;
    });

    // Sorting
    if (sortBy === "nama") {
      return base.sort((a, b) => a.namaPetugas.localeCompare(b.namaPetugas));
    } else if (sortBy === "realisasi_desc") {
      return base.sort((a, b) => b.realisasi - a.realisasi);
    } else if (sortBy === "realisasi_asc") {
      return base.sort((a, b) => a.realisasi - b.realisasi);
    } else if (sortBy === "pct_desc") {
      return base.sort((a, b) => {
        const pctA = a.total > 0 ? (a.realisasi / a.total) : 0;
        const pctB = b.total > 0 ? (b.realisasi / b.total) : 0;
        return pctB - pctA;
      });
    } else if (sortBy === "pct_asc") {
      return base.sort((a, b) => {
        const pctA = a.total > 0 ? (a.realisasi / a.total) : 0;
        const pctB = b.total > 0 ? (b.realisasi / b.total) : 0;
        return pctA - pctB;
      });
    }

    return base;
  }, [aggregatedStats, activeTab, selectedKec, searchQuery, sortBy]);

  // Filtered kecamatans list
  const filteredKecamatans = useMemo(() => {
    if (activeTab !== "kecamatan") return [];

    const base = kecamatanStats.filter(kec => {
      // Subdistrict filter
      if (selectedKec !== "all" && kec.namaKec !== selectedKec) {
        return false;
      }

      // Search query filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          kec.namaKec.toLowerCase().includes(query) ||
          kec.pmlList.some(p =>
            p.namaPetugas.toLowerCase().includes(query) ||
            p.email.toLowerCase().includes(query)
          )
        );
      }

      return true;
    });

    // Sorting
    if (sortBy === "nama") {
      return base.sort((a, b) => a.namaKec.localeCompare(b.namaKec));
    } else if (sortBy === "realisasi_desc") {
      return base.sort((a, b) => b.realisasi - a.realisasi);
    } else if (sortBy === "realisasi_asc") {
      return base.sort((a, b) => a.realisasi - b.realisasi);
    } else if (sortBy === "pct_desc") {
      return base.sort((a, b) => {
        const pctA = a.total > 0 ? (a.realisasi / a.total) : 0;
        const pctB = b.total > 0 ? (b.realisasi / b.total) : 0;
        return pctB - pctA;
      });
    } else if (sortBy === "pct_asc") {
      return base.sort((a, b) => {
        const pctA = a.total > 0 ? (a.realisasi / a.total) : 0;
        const pctB = b.total > 0 ? (b.realisasi / b.total) : 0;
        return pctA - pctB;
      });
    }

    return base;
  }, [kecamatanStats, activeTab, selectedKec, searchQuery, sortBy]);

  // Expand / collapse row handler
  const toggleRow = (email: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(email)) {
      newExpanded.delete(email);
    } else {
      newExpanded.add(email);
    }
    setExpandedRows(newExpanded);
  };

  // Export to CSV
  const handleExportCSV = () => {
    if (activeTab === "kecamatan") {
      const headers = [
        "Nama Kecamatan", "Jumlah PML", "Jumlah SLS", 
        "Total Target", "OPEN", "DRAFT", "SUBMITTED BY Pencacah", 
        "REJECTED BY Pengawas", "APPROVED BY Pengawas", "Progres / Realisasi", "Realisasi (%)"
      ];
      const csvRows = [headers.join(",")];

      filteredKecamatans.forEach(k => {
        const pct = k.total > 0 ? ((k.realisasi / k.total) * 100).toFixed(2) : "0.00";
        const row = [
          `"${formatKecName(k.namaKec).replace(/"/g, '""')}"`,
          k.pmlList.length,
          k.slsCount,
          k.total,
          k.open,
          k.draft,
          k.submit,
          k.reject,
          k.approve,
          k.realisasi,
          `"${pct}%"`
        ];
        csvRows.push(row.join(","));
      });

      const csvBlob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(csvBlob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", `monitoring_kecamatan_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return;
    }

    if (activeTab === "prioritas") {
      const headers = [
        "Kode SLS", "Kecamatan", "Koseka", "Pencacah (PCL)", "Pengawas (PML)", 
        "Total Target", "OPEN", "DRAFT", "SUBMITTED BY Pencacah", 
        "REJECTED BY Pengawas", "APPROVED BY Pengawas", "Progres", "Realisasi", "Realisasi (%)"
      ];
      const csvRows = [headers.join(",")];

      filteredPrioritySLS.forEach(item => {
        const pct = item.total > 0 ? ((item.realisasi / item.total) * 100).toFixed(2) : "0.00";
        const row = [
          `"${item.slsCode}"`,
          `"${formatKecName(item.namaKec).replace(/"/g, '""')}"`,
          `"${item.koseka.replace(/"/g, '""')}"`,
          `"${item.pencacah.replace(/"/g, '""')}"`,
          `"${item.pengawas.replace(/"/g, '""')}"`,
          item.total,
          item.open,
          item.draft,
          item.submit,
          item.reject,
          item.approve,
          item.progress,
          item.realisasi,
          `"${pct}%"`
        ];
        csvRows.push(row.join(","));
      });

      const csvBlob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(csvBlob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", `monitoring_prioritas_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return;
    }

    const headers = [
      "Nama Petugas", "Email", "Jabatan", "Kecamatan", "Koseka", 
      "Total Target", "OPEN", "DRAFT", "SUBMITTED BY Pencacah", 
      "REJECTED BY Pengawas", "APPROVED BY Pengawas", "Progres / Realisasi", "Realisasi (%)"
    ];
    const csvRows = [headers.join(",")];

    filteredOfficers.forEach(o => {
      const pct = o.total > 0 ? ((o.realisasi / o.total) * 100).toFixed(2) : "0.00";
      const row = [
        `"${o.namaPetugas.replace(/"/g, '""')}"`,
        `"${o.email.replace(/"/g, '""')}"`,
        `"${o.jabatanPetugas}"`,
        `"${formatKecName(o.namaKec).replace(/"/g, '""')}"`,
        `"${o.koseka.replace(/"/g, '""')}"`,
        o.total,
        o.open,
        o.draft,
        o.submit,
        o.reject,
        o.approve,
        o.realisasi,
        `"${pct}%"`
      ];
      csvRows.push(row.join(","));
    });

    const csvBlob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(csvBlob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `monitoring_petugas_${activeTab}_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Highlight rules functions
  const isPmlRed = (o: OfficerStats) => {
    // PML merah jika approve dan rejectnya masih 0
    return o.category.toLowerCase() === "pengawas" && o.approve === 0 && o.reject === 0;
  };

  const isPclRed = (o: OfficerStats) => {
    // PCL merah jika Draft, Submit, Reject, dan Approve = 0
    return (
      o.category.toLowerCase() === "pencacah" &&
      o.draft === 0 &&
      o.submit === 0 &&
      o.reject === 0 &&
      o.approve === 0
    );
  };

  return (
    <div className={`min-h-screen font-sans transition-colors duration-300 ${isDarkMode ? "dark bg-slate-950 text-slate-100" : "bg-slate-50 text-slate-900"}`}>
      
      {/* Header Bar */}
      <header className="sticky top-0 z-30 border-b backdrop-blur-md transition-colors bg-white/80 dark:bg-slate-900/80 border-slate-200 dark:border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
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
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
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
                className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-orange-500 text-white shadow-sm"
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
          <div className="absolute right-0 top-0 w-80 h-80 rounded-full bg-white/10 blur-3xl translate-x-20 -translate-y-20"></div>
          <div className="absolute right-1/4 bottom-0 w-60 h-60 rounded-full bg-orange-400/20 blur-2xl translate-y-20"></div>
          
          <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div>
              <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-white/20 text-white mb-3 inline-block">
                Monitoring Kinerja Petugas
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight mb-2">
                Monitoring Progres Petugas (Rekap)
              </h2>
              <p className="text-sm sm:text-lg text-orange-50 max-w-2xl font-light">
                Analisis detail capaian kinerja dari Pencacah (PCL/PPL) dan Pengawas (PML) secara real-time.
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
              Mengekstrak dan Memproses Data Petugas BPS FASIH...
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
            {/* View Selection & Search Panel */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 mb-8 shadow-sm flex flex-col gap-4">
              
              {/* Tab Selector & Actions */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-100 dark:border-slate-800/60 pb-4">
                
                {/* Tabs */}
                <div className="flex gap-1.5 p-1 bg-slate-100 dark:bg-slate-950 rounded-xl w-full sm:w-auto">
                  <button
                    onClick={() => {
                      setActiveTab("pcl");
                      setExpandedRows(new Set());
                    }}
                    className={`flex-1 sm:flex-initial flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-xs font-bold transition-all ${
                      activeTab === "pcl"
                        ? "bg-white dark:bg-slate-900 text-orange-500 shadow-sm"
                        : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                    }`}
                  >
                    <User className="w-4 h-4" />
                    Pencacah (PCL)
                  </button>
                  <button
                    onClick={() => {
                      setActiveTab("pml");
                      setExpandedRows(new Set());
                    }}
                    className={`flex-1 sm:flex-initial flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-xs font-bold transition-all ${
                      activeTab === "pml"
                        ? "bg-white dark:bg-slate-900 text-orange-500 shadow-sm"
                        : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                    }`}
                  >
                    <UserCheck className="w-4 h-4" />
                    Pengawas (PML)
                  </button>
                  <button
                    onClick={() => {
                      setActiveTab("kecamatan");
                      setExpandedRows(new Set());
                    }}
                    className={`flex-1 sm:flex-initial flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-xs font-bold transition-all ${
                      activeTab === "kecamatan"
                        ? "bg-white dark:bg-slate-900 text-orange-500 shadow-sm"
                        : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                    }`}
                  >
                    <Building className="w-4 h-4" />
                    Kecamatan
                  </button>
                  <button
                    onClick={() => {
                      setActiveTab("prioritas");
                      setExpandedRows(new Set());
                    }}
                    className={`flex-1 sm:flex-initial flex items-center justify-center gap-2 px-5 py-2 rounded-lg text-xs font-bold transition-all ${
                      activeTab === "prioritas"
                        ? "bg-white dark:bg-slate-900 text-orange-500 shadow-sm"
                        : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                    }`}
                  >
                    <Layers className="w-4 h-4" />
                    SLS Prioritas
                  </button>
                </div>

                {/* Actions */}
                <button
                  onClick={handleExportCSV}
                  className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm shadow-emerald-600/10"
                >
                  <Download className="w-4 h-4" />
                  Ekspor CSV
                </button>
              </div>

              {/* Filters Panel */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                
                {/* Search Bar */}
                <div className="md:col-span-6 relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Search className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    placeholder="Cari nama petugas, email, kecamatan, atau nama Koseka..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border bg-slate-50/50 dark:bg-slate-950/50 text-xs focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/80 outline-none transition-all border-slate-200 dark:border-slate-800"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200"
                    >
                      ×
                    </button>
                  )}
                </div>

                {/* Kecamatan Selector */}
                <div className="md:col-span-3 relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Filter className="w-4 h-4" />
                  </div>
                  <select
                    value={selectedKec}
                    onChange={(e) => setSelectedKec(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border bg-slate-50/50 dark:bg-slate-950/50 text-xs focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/80 outline-none transition-all border-slate-200 dark:border-slate-800 appearance-none text-slate-700 dark:text-slate-200"
                  >
                    <option value="all">Semua Kecamatan</option>
                    {subdistrictOptions.map(kec => (
                      <option key={kec} value={kec}>
                        {formatKecName(kec)}
                      </option>
                    ))}
                  </select>
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-400">
                    <ChevronDown className="w-4 h-4" />
                  </div>
                </div>

                {/* Sort Selector */}
                <div className="md:col-span-3 relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as any)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border bg-slate-50/50 dark:bg-slate-950/50 text-xs focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/80 outline-none transition-all border-slate-200 dark:border-slate-800 appearance-none text-slate-700 dark:text-slate-200"
                  >
                    <option value="nama">
                      {activeTab === "prioritas"
                        ? "Kode SLS (A-Z)"
                        : activeTab === "kecamatan"
                        ? "Nama Kecamatan (A-Z)"
                        : "Nama Petugas (A-Z)"}
                    </option>
                    <option value="realisasi_desc">Realisasi Terbesar (Jumlah)</option>
                    <option value="realisasi_asc">Realisasi Terkecil (Jumlah)</option>
                    <option value="pct_desc">Persentase Terbesar (%)</option>
                    <option value="pct_asc">Persentase Terkecil (%)</option>
                  </select>
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-400">
                    <ChevronDown className="w-4 h-4" />
                  </div>
                </div>
              </div>
            </div>

            {/* Warning Banner Info */}
            <div className="mb-6 p-4 rounded-xl border bg-amber-500/5 dark:bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400 text-xs flex gap-2.5 items-start">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <div>
                <span className="font-bold">Ketentuan Pewarnaan & Rekapitulasi:</span>
                <ul className="list-disc list-inside mt-1 flex flex-col gap-0.5">
                  {activeTab === "pcl" ? (
                    <li>
                      Untuk <span className="font-bold">Pencacah (PCL)</span>: Baris diwarnai <span className="text-red-500 font-bold">merah</span> jika status <span className="font-bold">DRAFT</span>, <span className="font-bold">SUBMIT</span>, <span className="font-bold">REJECT</span>, dan <span className="font-bold">APPROVE</span>-nya 0 (belum mulai bekerja).
                    </li>
                  ) : activeTab === "pml" ? (
                    <li>
                      Untuk <span className="font-bold">Pengawas (PML)</span>: Baris diwarnai <span className="text-red-500 font-bold">merah</span> jika status <span className="font-bold">APPROVE</span> dan <span className="font-bold">REJECT</span>-nya masih 0 (menandakan belum ada berkas yang diperiksa).
                    </li>
                  ) : activeTab === "kecamatan" ? (
                    <li>
                      Untuk <span className="font-bold">Kecamatan</span>: Baris diwarnai <span className="text-red-500 font-bold">merah</span> jika status <span className="font-bold">APPROVE</span> dan <span className="font-bold">REJECT</span>-nya masih 0 (menandakan belum ada berkas PML di kecamatan tersebut yang diperiksa).
                    </li>
                  ) : (
                    <li>
                      Untuk <span className="font-bold">SLS Prioritas</span>: Baris diwarnai dengan warna latar belakang <span className="text-orange-500 font-bold">oranye</span> premium. Nama PCL dan PML digabung, dan rekap menggunakan data Pengawas sebagai sumber utama.
                    </li>
                  )}
                  <li>
                    <span className="font-bold">Progres</span> dan <span className="font-bold">Realisasi</span> dihitung dari jumlah status yang bukan open (DRAFT + SUBMITTED + REJECTED + APPROVED).
                  </li>
                </ul>
              </div>
            </div>

            {/* Officers Data Table */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
              <div className="overflow-auto max-h-[650px] w-full">
                <table className="w-full text-left border-collapse">
                  <thead className="sticky top-0 z-20 bg-slate-50 dark:bg-slate-900 shadow-[0_1px_0_0_rgba(226,232,240,1)] dark:shadow-[0_1px_0_0_rgba(30,41,59,1)]">
                    <tr className="text-[10px] uppercase font-bold text-slate-500 dark:text-slate-400 tracking-wider">
                      {activeTab !== "prioritas" && (
                        <th className="py-4 px-4 w-10 bg-slate-50 dark:bg-slate-900"></th>
                      )}
                      <th className="py-4 px-2 w-12 text-center bg-slate-50 dark:bg-slate-900">No</th>
                      <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">
                        {activeTab === "prioritas"
                          ? "Kode SLS"
                          : activeTab === "kecamatan"
                          ? "Nama Kecamatan"
                          : "Nama Petugas"}
                      </th>
                      {activeTab === "prioritas" && (
                        <>
                          <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">Kecamatan</th>
                          <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">Koseka</th>
                          <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">Pencacah (PCL)</th>
                          <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">Pengawas (PML)</th>
                        </>
                      )}
                      {activeTab !== "kecamatan" && activeTab !== "prioritas" && (
                        <>
                          <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">Kecamatan</th>
                          <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">Koseka</th>
                          <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">SLS</th>
                        </>
                      )}
                      {activeTab === "kecamatan" && (
                        <>
                          <th className="py-4 px-4 bg-slate-50 dark:bg-slate-900">Jumlah PML</th>
                          <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">SLS</th>
                        </>
                      )}
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Target</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Open</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Draft</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Submit</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Reject</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Approve</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Progres</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">Realisasi</th>
                      <th className="py-4 px-4 text-center bg-slate-50 dark:bg-slate-900">% Realisasi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeTab === "kecamatan" ? (
                      filteredKecamatans.length === 0 ? (
                        <tr>
                          <td colSpan={14} className="py-10 text-center text-slate-500 dark:text-slate-400 text-xs">
                            Tidak ada data kecamatan yang cocok dengan filter atau pencarian Anda.
                          </td>
                        </tr>
                      ) : (
                        filteredKecamatans.map((k, index) => {
                          const isRed = k.approve === 0 && k.reject === 0;
                          const isExpanded = expandedRows.has(k.namaKec);
                          const pctRealisasi = k.total > 0 ? ((k.realisasi / k.total) * 100).toFixed(2) : "0.00";

                          return (
                            <React.Fragment key={k.namaKec}>
                              {/* Kecamatan Summary Row */}
                              <tr
                                className={`border-b border-slate-200 dark:border-slate-800/60 hover:bg-slate-50/50 dark:hover:bg-slate-950/10 transition-colors cursor-pointer text-xs ${
                                  isRed 
                                    ? "bg-red-500/5 dark:bg-red-500/10 text-red-600 dark:text-red-400 font-medium" 
                                    : ""
                                }`}
                                onClick={() => toggleRow(k.namaKec)}
                              >
                                <td className="py-3 px-4 text-center">
                                  {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-slate-400" />
                                  )}
                                </td>
                                <td className="py-3 px-2 text-center font-semibold text-slate-400 dark:text-slate-500">
                                  {index + 1}
                                </td>
                                <td className="py-3 px-4 font-semibold">
                                  {formatKecName(k.namaKec)}
                                </td>
                                <td className="py-3 px-4 font-normal">{k.pmlList.length} PML</td>
                                <td className="py-3 px-4 text-center font-normal">{k.slsCount}</td>
                                <td className="py-3 px-4 text-center font-semibold text-slate-800 dark:text-slate-200">{k.total}</td>
                                <td className="py-3 px-4 text-center font-normal text-amber-500/90">{k.open}</td>
                                <td className="py-3 px-4 text-center font-normal text-blue-500/90">{k.draft}</td>
                                <td className="py-3 px-4 text-center font-normal text-teal-500/90">{k.submit}</td>
                                <td className="py-3 px-4 text-center font-normal text-red-500/90">{k.reject}</td>
                                <td className="py-3 px-4 text-center font-normal text-emerald-500/90">{k.approve}</td>
                                <td className="py-3 px-4 text-center font-semibold text-slate-700 dark:text-slate-300">{k.progress}</td>
                                <td className="py-3 px-4 text-center font-semibold text-slate-700 dark:text-slate-300">{k.realisasi}</td>
                                <td className="py-3 px-4 text-center">
                                  <span className={`inline-flex px-2.5 py-0.5 rounded-full font-extrabold text-xs ${
                                    isRed
                                      ? "bg-red-500/10 text-red-500 border border-red-500/20"
                                      : parseFloat(pctRealisasi) >= 80
                                      ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                                      : parseFloat(pctRealisasi) >= 40
                                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                      : "bg-slate-500/10 text-slate-400 border border-slate-500/20"
                                  }`}>
                                    {pctRealisasi}%
                                  </span>
                                </td>
                              </tr>

                              {/* Expanded PML List in Kecamatan Row */}
                              {isExpanded && (
                                <tr className="bg-slate-50/20 dark:bg-slate-950/20 border-b border-slate-200 dark:border-slate-800">
                                  <td colSpan={14} className="py-4 px-8">
                                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 p-4 shadow-inner">
                                      <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
                                        <UserCheck className="w-3.5 h-3.5 text-orange-500" />
                                        Daftar PML di Kecamatan {formatKecName(k.namaKec)}
                                      </h4>
                                      <div className="overflow-x-auto">
                                        <table className="w-full text-left border-collapse text-[11px]">
                                          <thead>
                                            <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 font-bold uppercase tracking-wider text-[9px]">
                                              <th className="pb-2 font-bold">Nama PML</th>
                                              <th className="pb-2 font-bold">Email</th>
                                              <th className="pb-2 text-center font-bold">SLS</th>
                                              <th className="pb-2 text-center font-bold">Target</th>
                                              <th className="pb-2 text-center font-bold">Open</th>
                                              <th className="pb-2 text-center font-bold">Draft</th>
                                              <th className="pb-2 text-center font-bold">Submit</th>
                                              <th className="pb-2 text-center font-bold">Reject</th>
                                              <th className="pb-2 text-center font-bold">Approve</th>
                                              <th className="pb-2 text-center font-bold">Progres</th>
                                              <th className="pb-2 text-center font-bold">Realisasi</th>
                                              <th className="pb-2 text-center font-bold">% Realisasi</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {k.pmlList.map((pml) => {
                                              const pmlPct = pml.total > 0 ? ((pml.realisasi / pml.total) * 100).toFixed(2) : "0.00";
                                              const isPmlRedRow = pml.approve === 0 && pml.reject === 0;
                                              return (
                                                <tr
                                                  key={pml.email}
                                                  className={`border-b border-slate-100 dark:border-slate-800/40 py-2 hover:bg-slate-50/50 dark:hover:bg-slate-950/10 transition-colors ${
                                                    isPmlRedRow
                                                      ? "bg-red-500/5 dark:bg-red-500/10 text-red-600 dark:text-red-400 font-medium"
                                                      : ""
                                                  }`}
                                                >
                                                  <td className="py-2 font-semibold">{pml.namaPetugas}</td>
                                                  <td className="py-2 text-slate-400 font-normal">{pml.email}</td>
                                                  <td className="py-2 text-center">{pml.slsCount}</td>
                                                  <td className="py-2 text-center font-semibold text-slate-800 dark:text-slate-200">{pml.total}</td>
                                                  <td className="py-2 text-center text-amber-500/90">{pml.open}</td>
                                                  <td className="py-2 text-center text-blue-500/90">{pml.draft}</td>
                                                  <td className="py-2 text-center text-teal-500/90">{pml.submit}</td>
                                                  <td className="py-2 text-center text-red-500/90">{pml.reject}</td>
                                                  <td className="py-2 text-center text-emerald-500/90">{pml.approve}</td>
                                                  <td className="py-2 text-center font-semibold text-slate-700 dark:text-slate-300">{pml.progress}</td>
                                                  <td className="py-2 text-center font-semibold text-slate-700 dark:text-slate-300">{pml.realisasi}</td>
                                                  <td className="py-2 text-center">
                                                    <span className={`inline-flex px-2 py-0.5 rounded-full font-extrabold text-[10px] ${
                                                      isPmlRedRow
                                                        ? "bg-red-500/10 text-red-500 border border-red-500/20"
                                                        : parseFloat(pmlPct) >= 80
                                                        ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                                                        : parseFloat(pmlPct) >= 40
                                                        ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                                        : "bg-slate-500/10 text-slate-400 border border-slate-500/20"
                                                    }`}>
                                                      {pmlPct}%
                                                    </span>
                                                  </td>
                                                </tr>
                                              );
                                            })}
                                          </tbody>
                                        </table>
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })
                      )
                    ) : activeTab === "prioritas" ? (
                      filteredPrioritySLS.length === 0 ? (
                        <tr>
                          <td colSpan={15} className="py-10 text-center text-slate-500 dark:text-slate-400 text-xs">
                            Tidak ada data SLS Prioritas yang cocok dengan filter atau pencarian Anda.
                          </td>
                        </tr>
                      ) : (
                        filteredPrioritySLS.map((item, index) => {
                          const pctRealisasi = item.total > 0 ? ((item.realisasi / item.total) * 100).toFixed(2) : "0.00";
                          return (
                            <tr
                              key={item.slsCode}
                              className="border-b border-orange-500/20 dark:border-orange-500/10 bg-orange-500/[0.03] dark:bg-orange-500/[0.015] hover:bg-orange-500/[0.06] dark:hover:bg-orange-500/[0.03] transition-colors text-xs border-l-4 border-l-orange-500"
                            >
                              <td className="py-3 px-2 text-center font-semibold text-slate-400 dark:text-slate-500">
                                {index + 1}
                              </td>
                              <td className="py-3 px-4 font-bold text-slate-900 dark:text-slate-100 font-mono">
                                {item.slsCode}
                              </td>
                              <td className="py-3 px-4 font-normal text-slate-700 dark:text-slate-300">
                                {formatKecName(item.namaKec)}
                              </td>
                              <td className="py-3 px-4 font-normal text-slate-700 dark:text-slate-300">
                                {item.koseka}
                              </td>
                              <td className="py-3 px-4 font-semibold text-slate-800 dark:text-slate-200">
                                {item.pencacah}
                              </td>
                              <td className="py-3 px-4 font-semibold text-slate-800 dark:text-slate-200">
                                {item.pengawas}
                              </td>
                              <td className="py-3 px-4 text-center font-semibold text-slate-800 dark:text-slate-200">
                                {item.total}
                              </td>
                              <td className="py-3 px-4 text-center font-normal text-amber-500/90">
                                {item.open}
                              </td>
                              <td className="py-3 px-4 text-center font-normal text-blue-500/90">
                                {item.draft}
                              </td>
                              <td className="py-3 px-4 text-center font-normal text-teal-500/90">
                                {item.submit}
                              </td>
                              <td className="py-3 px-4 text-center font-normal text-red-500/90">
                                {item.reject}
                              </td>
                              <td className="py-3 px-4 text-center font-normal text-emerald-500/90">
                                {item.approve}
                              </td>
                              <td className="py-3 px-4 text-center font-semibold text-slate-700 dark:text-slate-300">
                                {item.progress}
                              </td>
                              <td className="py-3 px-4 text-center font-semibold text-slate-700 dark:text-slate-300">
                                {item.realisasi}
                              </td>
                              <td className="py-3 px-4 text-center">
                                <span className={`inline-flex px-2.5 py-0.5 rounded-full font-extrabold text-xs bg-orange-500/10 text-orange-500 border border-orange-500/20`}>
                                  {pctRealisasi}%
                                </span>
                              </td>
                            </tr>
                          );
                        })
                      )
                    ) : (
                      filteredOfficers.length === 0 ? (
                        <tr>
                          <td colSpan={15} className="py-10 text-center text-slate-500 dark:text-slate-400 text-xs">
                            Tidak ada data petugas yang cocok dengan filter atau pencarian Anda.
                          </td>
                        </tr>
                      ) : (
                        filteredOfficers.map((o, index) => {
                          const isRed = activeTab === "pcl" ? isPclRed(o) : isPmlRed(o);
                          const isExpanded = expandedRows.has(o.email);
                          const pctRealisasi = o.total > 0 ? ((o.realisasi / o.total) * 100).toFixed(2) : "0.00";

                          return (
                            <React.Fragment key={o.email}>
                              {/* Officer Summary Row */}
                              <tr
                                className={`border-b border-slate-200 dark:border-slate-800/60 hover:bg-slate-50/50 dark:hover:bg-slate-950/10 transition-colors cursor-pointer text-xs ${
                                  isRed 
                                    ? "bg-red-500/5 dark:bg-red-500/10 text-red-600 dark:text-red-400 font-medium" 
                                    : ""
                                }`}
                                onClick={() => toggleRow(o.email)}
                              >
                                <td className="py-3 px-4 text-center">
                                  {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-slate-400" />
                                  )}
                                </td>
                                <td className="py-3 px-2 text-center font-semibold text-slate-400 dark:text-slate-500">
                                  {index + 1}
                                </td>
                                <td className="py-3 px-4 font-semibold">
                                  <div>{o.namaPetugas}</div>
                                  <div className="text-[10px] text-slate-400 font-normal mt-0.5">{o.email}</div>
                                </td>
                                <td className="py-3 px-4 font-normal">{formatKecName(o.namaKec)}</td>
                                <td className="py-3 px-4 font-normal">{o.koseka}</td>
                                <td className="py-3 px-4 text-center font-normal">{o.slsList.length}</td>
                                <td className="py-3 px-4 text-center font-semibold text-slate-800 dark:text-slate-200">{o.total}</td>
                                <td className="py-3 px-4 text-center font-normal text-amber-500/90">{o.open}</td>
                                <td className="py-3 px-4 text-center font-normal text-blue-500/90">{o.draft}</td>
                                <td className="py-3 px-4 text-center font-normal text-teal-500/90">{o.submit}</td>
                                <td className="py-3 px-4 text-center font-normal text-red-500/90">{o.reject}</td>
                                <td className="py-3 px-4 text-center font-normal text-emerald-500/90">{o.approve}</td>
                                <td className="py-3 px-4 text-center font-semibold text-slate-700 dark:text-slate-300">{o.progress}</td>
                                <td className="py-3 px-4 text-center font-semibold text-slate-700 dark:text-slate-300">{o.realisasi}</td>
                                <td className="py-3 px-4 text-center">
                                  <span className={`inline-flex px-2.5 py-0.5 rounded-full font-extrabold text-xs ${
                                    isRed
                                      ? "bg-red-500/10 text-red-500 border border-red-500/20"
                                      : parseFloat(pctRealisasi) >= 80
                                      ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                                      : parseFloat(pctRealisasi) >= 40
                                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                      : "bg-slate-500/10 text-slate-400 border border-slate-500/20"
                                  }`}>
                                    {pctRealisasi}%
                                  </span>
                                </td>
                              </tr>

                              {/* Expanded SLS Detail Row */}
                              {isExpanded && (
                                <tr className="bg-slate-50/20 dark:bg-slate-950/20 border-b border-slate-200 dark:border-slate-800">
                                  <td colSpan={15} className="py-4 px-8">
                                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 p-4 shadow-inner">
                                      <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
                                        <Layers className="w-3.5 h-3.5 text-orange-500" />
                                        Detail SLS untuk {o.namaPetugas}
                                      </h4>
                                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                                        {o.slsList.map((sls) => {
                                          const slsPct = sls.total > 0 ? ((sls.progress / sls.total) * 100).toFixed(2) : "0.00";
                                          return (
                                            <div
                                              key={sls.slsCode}
                                              className={`p-3.5 rounded-xl border flex flex-col gap-2.5 shadow-sm hover:shadow transition-all ${
                                                sls.isPrioritas
                                                  ? "border-orange-500/60 dark:border-orange-500/40 bg-orange-500/[0.02] dark:bg-orange-500/[0.01] ring-1 ring-orange-500/20"
                                                  : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950"
                                              }`}
                                            >
                                              <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-1.5">
                                                <span className="font-bold text-xs text-slate-900 dark:text-slate-200 font-mono tracking-tight flex items-center gap-1.5">
                                                  {sls.slsCode}
                                                  {sls.isPrioritas && (
                                                    <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" title="SLS Prioritas"></span>
                                                  )}
                                                </span>
                                                <div className="flex items-center gap-1.5">
                                                  {sls.isPrioritas && (
                                                    <span className="text-[8px] font-black text-orange-600 dark:text-orange-400 bg-orange-500/10 px-1 py-0.2 rounded uppercase tracking-wider">
                                                      Prio
                                                    </span>
                                                  )}
                                                  <span className="text-xs font-extrabold text-orange-500 bg-orange-500/10 px-2 py-0.5 rounded">
                                                    {slsPct}%
                                                  </span>
                                                </div>
                                              </div>
                                              <div className="grid grid-cols-2 gap-y-1.5 gap-x-2 text-[10px] text-slate-500">
                                                <div className="flex justify-between">
                                                  <span>Target:</span>
                                                  <span className="font-bold text-slate-800 dark:text-slate-300">{sls.total}</span>
                                                </div>
                                                <div className="flex justify-between text-amber-500">
                                                  <span>Open:</span>
                                                  <span className="font-bold">{sls.open}</span>
                                                </div>
                                                <div className="flex justify-between text-blue-500">
                                                  <span>Draft:</span>
                                                  <span className="font-bold">{sls.draft}</span>
                                                </div>
                                                <div className="flex justify-between text-teal-500">
                                                  <span>Submit:</span>
                                                  <span className="font-bold">{sls.submit}</span>
                                                </div>
                                                <div className="flex justify-between text-red-500">
                                                  <span>Reject:</span>
                                                  <span className="font-bold">{sls.reject}</span>
                                                </div>
                                                <div className="flex justify-between text-emerald-500">
                                                  <span>Approve:</span>
                                                  <span className="font-bold">{sls.approve}</span>
                                                </div>
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })
                      )
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
