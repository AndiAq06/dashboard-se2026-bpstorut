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
  Layers,
  ChevronDown,
  X,
  TrendingUp,
  SlidersHorizontal,
  ChevronRight,
  BookOpen
} from "lucide-react";

// Interfaces for data types
interface ScraperRecord {
  searchedEmail: string;
  idCode: string;
  name: string;
  address: string;
  scale: string;
  status: string;
  officer: string;
  nama_kec: string;
  koseka: string;
  isPrioritas: string;
}

interface PMLPPLRecord {
  nama_petugas: string;
  kec: string;
  jabatan_petugas: string; // 'PML' or 'PPL'
  email: string;
}

interface CellStats {
  target: number;
  realisasi: number;
  open: number;
  draft: number;
  submit: number;
  approve: number;
  reject: number;
}

interface RowStats {
  nama: string;
  email: string;
  kec: string;
  jabatan: string;
  categories: { [category: string]: CellStats };
  total: CellStats;
}

interface KecStats {
  kecName: string;
  koseka: string;
  categories: { [category: string]: CellStats };
  total: CellStats;
}

interface SLSStats {
  slsCode: string;
  kec: string;
  koseka: string;
  isPrioritas: boolean;
  categories: { [category: string]: CellStats };
  total: CellStats;
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

export default function TabulasiPage() {
  // Theme state
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Data states
  const [rawData, setRawData] = useState<ScraperRecord[]>([]);
  const [pmlPplData, setPmlPplData] = useState<PMLPPLRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  // Filter & Search states
  const [selectedKec, setSelectedKec] = useState<string>("all");
  const [selectedPml, setSelectedPml] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"pcl" | "pml" | "kec" | "sls">("pcl");

  // SLS pagination states
  const [slsPage, setSlsPage] = useState(1);
  const slsPerPage = 25;

  useEffect(() => {
    setSlsPage(1);
  }, [selectedKec, searchQuery, activeTab]);

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
  }, [rawData, activeTab, selectedKec, selectedPml, searchQuery, slsPage]);

  // Helper to normalize subdistrict/kecamatan names for comparison
  const normalizeKec = (name: string): string => {
    if (!name) return "";
    return name.replace(/\(\d+\)/g, "").trim().toUpperCase();
  };

  // Helper to format subdistrict/kecamatan names to Title Case and strip BPS codes
  const formatKecName = (name: string): string => {
    if (!name) return "";
    let cleaned = name.replace(/\(\d+\)/g, "").trim();
    return cleaned
      .toLowerCase()
      .split(" ")
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  // Fetch and parse data
  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch update_data.csv
      const dataResponse = await fetch("/update_data.csv");
      if (!dataResponse.ok) {
        throw new Error("Gagal mengambil file update_data.csv. Pastikan pipeline data sudah dijalankan.");
      }
      const dataText = await dataResponse.text();

      // Fetch pml_ppl.csv
      const pmlPplResponse = await fetch("/pml_ppl.csv");
      if (!pmlPplResponse.ok) {
        throw new Error("Gagal mengambil file pml_ppl.csv.");
      }
      const pmlPplText = await pmlPplResponse.text();

      // Parse update_data.csv
      const parseDataCSV = (csvText: string): ScraperRecord[] => {
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
          row.push(entry);

          if (row.length >= 16 && row[1] && row[1].trim() !== "" && row[1] !== "Kode Identitas") {
            parsed.push({
              searchedEmail: row[0].replace(/"/g, "").trim().toLowerCase(),
              idCode: row[1].replace(/"/g, "").trim(),
              name: row[2].replace(/"/g, "").trim(),
              address: row[3].replace(/"/g, "").trim(),
              scale: normalizeScale(row[7].replace(/"/g, "").trim()),
              status: row[12].replace(/"/g, "").trim(),
              officer: row[14].replace(/"/g, "").trim(),
              nama_kec: row[16] ? row[16].replace(/"/g, "").trim() : "",
              koseka: row[17] ? row[17].replace(/"/g, "").trim() : "",
              isPrioritas: row[18] ? row[18].replace(/"/g, "").trim() : "Tidak",
            });
          }
        }
        return parsed;
      };

      // Parse pml_ppl.csv (semicolon delimited)
      const parsePMLPPL = (csvText: string): PMLPPLRecord[] => {
        const lines = csvText.split("\n");
        const parsed: PMLPPLRecord[] = [];

        for (let i = 1; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          const parts = line.split(";");
          if (parts.length >= 4) {
            parsed.push({
              nama_petugas: parts[0].replace(/"/g, "").trim(),
              kec: parts[1].replace(/"/g, "").trim(),
              jabatan_petugas: parts[2].replace(/"/g, "").trim().toUpperCase(),
              email: parts[3].replace(/"/g, "").trim().toLowerCase(),
            });
          }
        }
        return parsed;
      };

      const parsedRecords = parseDataCSV(dataText);
      const parsedPmlPpl = parsePMLPPL(pmlPplText);

      setRawData(parsedRecords);
      setPmlPplData(parsedPmlPpl);

      // Load timestamp
      let loadedTimestamp = "";
      try {
        const timeResponse = await fetch("/last_updated.txt");
        if (timeResponse.ok) {
          loadedTimestamp = (await timeResponse.text()).trim();
        }
      } catch (e) {
        console.warn("Gagal mengambil file last_updated.txt.");
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

  // Scale Category Mapping
  const categories = useMemo(() => [
    "Keluarga",
    "UMK",
    "UMKM Bangunan Lain",
    "UM",
    "UB",
    "UMKM/Dummy",
    "UMKM/Keluarga"
  ], []);

  const getScaleCategory = (scale: string): string => {
    return scale;
  };

  // Helper to initialize empty CellStats
  const createEmptyCellStats = (): CellStats => ({
    target: 0,
    realisasi: 0,
    open: 0,
    draft: 0,
    submit: 0,
    approve: 0,
    reject: 0
  });

  // Unique lists from both data sources
  const uniqueKecList = useMemo(() => {
    const formattedSubdistricts = rawData.map(r => formatKecName(r.nama_kec)).filter(Boolean);
    const formattedAllKecs = pmlPplData.map(item => formatKecName(item.kec)).filter(Boolean);
    return Array.from(new Set([...formattedSubdistricts, ...formattedAllKecs])).sort();
  }, [rawData, pmlPplData]);

  // List of PMLs filtered by selected Kecamatan
  const pmlList = useMemo(() => {
    return pmlPplData.filter(item => {
      const matchRole = item.jabatan_petugas === "PML";
      const matchKec = selectedKec === "all" ? true : normalizeKec(item.kec) === normalizeKec(selectedKec);
      return matchRole && matchKec;
    }).sort((a, b) => a.nama_petugas.localeCompare(b.nama_petugas));
  }, [pmlPplData, selectedKec]);

  // Reset PML filter if selected Kecamatan changes and currently selected PML is not in new list
  useEffect(() => {
    if (selectedPml !== "all") {
      const pmlExists = pmlList.some(p => p.nama_petugas === selectedPml);
      if (!pmlExists) {
        setSelectedPml("all");
      }
    }
  }, [selectedKec, pmlList, selectedPml]);

  // If PML is selected, automatically update selectedKec to PML's Kecamatan
  const handlePmlChange = (pmlName: string) => {
    setSelectedPml(pmlName);
    if (pmlName !== "all") {
      const selectedPmlRecord = pmlPplData.find(item => item.nama_petugas === pmlName);
      if (selectedPmlRecord) {
        setSelectedKec(selectedPmlRecord.kec);
      }
    }
  };

  // Calculate Table 1: PCL (PPL) detail stats
  const pclStats = useMemo<RowStats[]>(() => {
    // 1. Get PPLs
    const ppls = pmlPplData.filter(item => item.jabatan_petugas === "PPL");

    // 2. Pre-filter PPLs by selected Kecamatan / PML
    const filteredPpls = ppls.filter(ppl => {
      const matchKec = selectedKec === "all" ? true : normalizeKec(ppl.kec) === normalizeKec(selectedKec);
      return matchKec;
    });

    // 3. Map PPLs to their stats
    const stats: RowStats[] = filteredPpls.map(ppl => {
      const pplEmail = ppl.email.toLowerCase();
      // Filter records for this PPL
      const records = rawData.filter(r => r.searchedEmail === pplEmail);

      const rowStats: RowStats = {
        nama: ppl.nama_petugas,
        email: ppl.email,
        kec: ppl.kec,
        jabatan: ppl.jabatan_petugas,
        categories: {},
        total: createEmptyCellStats()
      };

      // Initialize categories
      categories.forEach(cat => {
        rowStats.categories[cat] = createEmptyCellStats();
      });

      // Aggregate records
      records.forEach(r => {
        const cat = getScaleCategory(r.scale);
        const status = r.status.toLowerCase().trim();

        // Process status checks
        const isOpen = status === "open" || status === "";
        const isDraft = status === "draft";
        const isSubmit = status === "submitted by pencacah" || status === "submit" || status === "submitted";
        const isApprove = status === "approve" || status === "approved" || status === "approved by pengawas";
        const isReject = status === "rejected by pengawas" || status === "reject" || status === "rejected";
        const isRealisasi = isSubmit || isReject || isApprove;

        // Helper to add stats
        const addStats = (cell: CellStats) => {
          cell.target++;
          if (isRealisasi) cell.realisasi++;
          if (isOpen) cell.open++;
          if (isDraft) cell.draft++;
          if (isSubmit) cell.submit++;
          if (isApprove) cell.approve++;
          if (isReject) cell.reject++;
        };

        // Add to category
        if (cat && rowStats.categories[cat]) {
          addStats(rowStats.categories[cat]);
        }
        // Add to total
        addStats(rowStats.total);
      });

      return rowStats;
    });

    // Sort by name
    return stats.sort((a, b) => a.nama.localeCompare(b.nama));
  }, [rawData, pmlPplData, selectedKec, categories]);

  // Filtered Table 1 based on search query
  const filteredPclStats = useMemo(() => {
    return pclStats.filter(pcl => {
      if (!searchQuery) return true;
      return pcl.nama.toLowerCase().includes(searchQuery.toLowerCase()) || 
             pcl.kec.toLowerCase().includes(searchQuery.toLowerCase());
    });
  }, [pclStats, searchQuery]);

  // Calculate Table 3: PML (Pengawas) detail stats
  const pmlStats = useMemo<RowStats[]>(() => {
    // 1. Get PMLs
    const pmls = pmlPplData.filter(item => item.jabatan_petugas === "PML");

    // 2. Pre-filter PMLs by selected Kecamatan / PML filter
    const filteredPmls = pmls.filter(pml => {
      const matchKec = selectedKec === "all" ? true : normalizeKec(pml.kec) === normalizeKec(selectedKec);
      const matchPml = selectedPml === "all" ? true : pml.nama_petugas === selectedPml;
      return matchKec && matchPml;
    });

    // 3. Map PMLs to their stats (aggregated from PPLs in the same Kecamatan)
    const stats: RowStats[] = filteredPmls.map(pml => {
      const normalizedKecName = normalizeKec(pml.kec);
      
      // Get all PPLs in the same subdistrict
      const pplsInKec = pmlPplData.filter(item => item.jabatan_petugas === "PPL" && normalizeKec(item.kec) === normalizedKecName);
      const emailsInKec = new Set(pplsInKec.map(ppl => ppl.email.toLowerCase()));

      // Get records for these PPLs
      const records = rawData.filter(r => emailsInKec.has(r.searchedEmail) || normalizeKec(r.nama_kec) === normalizedKecName);

      const rowStats: RowStats = {
        nama: pml.nama_petugas,
        email: pml.email,
        kec: pml.kec,
        jabatan: pml.jabatan_petugas,
        categories: {},
        total: createEmptyCellStats()
      };

      // Initialize categories
      categories.forEach(cat => {
        rowStats.categories[cat] = createEmptyCellStats();
      });

      // Aggregate records
      records.forEach(r => {
        const cat = getScaleCategory(r.scale);
        const status = r.status.toLowerCase().trim();

        const isOpen = status === "open" || status === "";
        const isDraft = status === "draft";
        const isSubmit = status === "submitted by pencacah" || status === "submit" || status === "submitted";
        const isApprove = status === "approve" || status === "approved" || status === "approved by pengawas";
        const isReject = status === "rejected by pengawas" || status === "reject" || status === "rejected";
        const isRealisasi = isSubmit || isReject || isApprove;

        const addStats = (cell: CellStats) => {
          cell.target++;
          if (isRealisasi) cell.realisasi++;
          if (isOpen) cell.open++;
          if (isDraft) cell.draft++;
          if (isSubmit) cell.submit++;
          if (isApprove) cell.approve++;
          if (isReject) cell.reject++;
        };

        if (cat && rowStats.categories[cat]) {
          addStats(rowStats.categories[cat]);
        }
        addStats(rowStats.total);
      });

      return rowStats;
    });

    return stats.sort((a, b) => a.nama.localeCompare(b.nama));
  }, [rawData, pmlPplData, selectedKec, selectedPml, categories]);

  // Filtered Table 3 based on search query
  const filteredPmlStats = useMemo(() => {
    return pmlStats.filter(pml => {
      if (!searchQuery) return true;
      return pml.nama.toLowerCase().includes(searchQuery.toLowerCase()) || 
             pml.kec.toLowerCase().includes(searchQuery.toLowerCase());
    });
  }, [pmlStats, searchQuery]);

  // Overview stats for PML tab (prevents double counting)
  const selectedPmlOverviewStats = useMemo(() => {
    const totalStats = createEmptyCellStats();
    
    // Find the unique kecamatan names of all currently visible PMLs
    const visibleKecs = new Set(filteredPmlStats.map(pml => normalizeKec(pml.kec)));
    
    // Find unique PPLs in these kecamatans
    const ppls = pmlPplData.filter(item => item.jabatan_petugas === "PPL" && visibleKecs.has(normalizeKec(item.kec)));
    const pplEmails = new Set(ppls.map(p => p.email.toLowerCase()));
    
    // Sum stats of records for these PPLs
    const records = rawData.filter(r => pplEmails.has(r.searchedEmail) || visibleKecs.has(normalizeKec(r.nama_kec)));
    
    records.forEach(r => {
      const status = r.status.toLowerCase().trim();
      const isOpen = status === "open" || status === "";
      const isDraft = status === "draft";
      const isSubmit = status === "submitted by pencacah" || status === "submit" || status === "submitted";
      const isApprove = status === "approve" || status === "approved" || status === "approved by pengawas";
      const isReject = status === "rejected by pengawas" || status === "reject" || status === "rejected";
      const isRealisasi = isSubmit || isReject || isApprove;

      totalStats.target++;
      if (isRealisasi) totalStats.realisasi++;
      if (isOpen) totalStats.open++;
      if (isDraft) totalStats.draft++;
      if (isSubmit) totalStats.submit++;
      if (isApprove) totalStats.approve++;
      if (isReject) totalStats.reject++;
    });
    
    const completionRate = totalStats.target > 0 ? (totalStats.realisasi / totalStats.target) * 100 : 0;
    
    return {
      ...totalStats,
      completionRate
    };
  }, [rawData, pmlPplData, filteredPmlStats]);

  // Calculate Table 4: SLS Overview stats
  const slsStats = useMemo<SLSStats[]>(() => {
    const statsMap: { [slsCode: string]: SLSStats } = {};

    rawData.forEach(r => {
      const digits = r.idCode.replace(/\D/g, "");
      if (digits.length < 14) return;
      const slsCode = digits.substring(0, 14);

      if (!statsMap[slsCode]) {
        statsMap[slsCode] = {
          slsCode,
          kec: formatKecName(r.nama_kec),
          koseka: r.koseka,
          isPrioritas: r.isPrioritas === "Ya",
          categories: {},
          total: createEmptyCellStats()
        };
        categories.forEach(cat => {
          statsMap[slsCode].categories[cat] = createEmptyCellStats();
        });
      }

      const cat = getScaleCategory(r.scale);
      const status = r.status.toLowerCase().trim();

      const isOpen = status === "open" || status === "";
      const isDraft = status === "draft";
      const isSubmit = status === "submitted by pencacah" || status === "submit" || status === "submitted";
      const isApprove = status === "approve" || status === "approved" || status === "approved by pengawas";
      const isReject = status === "rejected by pengawas" || status === "reject" || status === "rejected";
      const isRealisasi = isSubmit || isReject || isApprove;

      const addStats = (cell: CellStats) => {
        cell.target++;
        if (isRealisasi) cell.realisasi++;
        if (isOpen) cell.open++;
        if (isDraft) cell.draft++;
        if (isSubmit) cell.submit++;
        if (isApprove) cell.approve++;
        if (isReject) cell.reject++;
      };

      if (cat && statsMap[slsCode].categories[cat]) {
        addStats(statsMap[slsCode].categories[cat]);
      }
      addStats(statsMap[slsCode].total);
    });

    return Object.values(statsMap).sort((a, b) => a.slsCode.localeCompare(b.slsCode));
  }, [rawData, categories]);

  // Filtered Table 4 based on search query and selected filters
  const filteredSlsStats = useMemo(() => {
    return slsStats.filter(sls => {
      const matchKec = selectedKec === "all" ? true : normalizeKec(sls.kec) === normalizeKec(selectedKec);
      if (!matchKec) return false;

      if (!searchQuery) return true;
      const query = searchQuery.toLowerCase();
      return sls.slsCode.includes(query) || sls.kec.toLowerCase().includes(query);
    });
  }, [slsStats, selectedKec, searchQuery]);

  // Overview stats for SLS tab (prevents double counting)
  const selectedSlsOverviewStats = useMemo(() => {
    const totalStats = createEmptyCellStats();

    filteredSlsStats.forEach(sls => {
      const t = sls.total;
      totalStats.target += t.target;
      totalStats.realisasi += t.realisasi;
      totalStats.open += t.open;
      totalStats.draft += t.draft;
      totalStats.submit += t.submit;
      totalStats.approve += t.approve;
      totalStats.reject += t.reject;
    });

    const completionRate = totalStats.target > 0 ? (totalStats.realisasi / totalStats.target) * 100 : 0;

    return {
      ...totalStats,
      completionRate
    };
  }, [filteredSlsStats]);

  const paginatedSlsStats = useMemo(() => {
    const startIndex = (slsPage - 1) * slsPerPage;
    return filteredSlsStats.slice(startIndex, startIndex + slsPerPage);
  }, [filteredSlsStats, slsPage]);

  const totalSlsPages = Math.ceil(filteredSlsStats.length / slsPerPage) || 1;

  // Calculate Table 2: Kecamatan Overview stats
  const kecamatanStats = useMemo<KecStats[]>(() => {
    const statsMap: { [kecName: string]: KecStats } = {};

    // Load subdistrict names from koseka mapping or scraped data
    const subdistricts = rawData.map(r => formatKecName(r.nama_kec)).filter(Boolean);
    
    // Fallback: load all Kec from pml_ppl.csv
    const allKecs = pmlPplData.map(item => formatKecName(item.kec)).filter(Boolean);
    const uniqueKecNames = Array.from(new Set([...subdistricts, ...allKecs])).sort();

    // Helper to get koseka name for a kecamatan
    const getKosekaForKec = (kecName: string): string => {
      const normalized = normalizeKec(kecName);
      const record = rawData.find(r => normalizeKec(r.nama_kec) === normalized);
      return record ? record.koseka : "-";
    };

    uniqueKecNames.forEach(kec => {
      const normalizedKecName = normalizeKec(kec);
      
      const kecStats: KecStats = {
        kecName: kec, // formatted Title Case name
        koseka: getKosekaForKec(kec),
        categories: {},
        total: createEmptyCellStats()
      };

      categories.forEach(cat => {
        kecStats.categories[cat] = createEmptyCellStats();
      });

      // Find PPL emails in this Kecamatan
      const pplsInKec = pmlPplData.filter(item => item.jabatan_petugas === "PPL" && normalizeKec(item.kec) === normalizedKecName);
      const emailsInKec = new Set(pplsInKec.map(ppl => ppl.email.toLowerCase()));

      // Aggregate records where searchedEmail is in this subdistrict
      const records = rawData.filter(r => emailsInKec.has(r.searchedEmail) || normalizeKec(r.nama_kec) === normalizedKecName);

      records.forEach(r => {
        const cat = getScaleCategory(r.scale);
        const status = r.status.toLowerCase().trim();

        const isOpen = status === "open" || status === "";
        const isDraft = status === "draft";
        const isSubmit = status === "submitted by pencacah" || status === "submit" || status === "submitted";
        const isApprove = status === "approve" || status === "approved" || status === "approved by pengawas";
        const isReject = status === "rejected by pengawas" || status === "reject" || status === "rejected";
        const isRealisasi = isSubmit || isReject || isApprove;

        const addStats = (cell: CellStats) => {
          cell.target++;
          if (isRealisasi) cell.realisasi++;
          if (isOpen) cell.open++;
          if (isDraft) cell.draft++;
          if (isSubmit) cell.submit++;
          if (isApprove) cell.approve++;
          if (isReject) cell.reject++;
        };

        if (cat && kecStats.categories[cat]) {
          addStats(kecStats.categories[cat]);
        }
        addStats(kecStats.total);
      });

      statsMap[kec] = kecStats;
    });

    return Object.values(statsMap).sort((a, b) => a.kecName.localeCompare(b.kecName));
  }, [rawData, pmlPplData, categories]);

  // Overall Statistics for Selected View
  const selectedOverviewStats = useMemo(() => {
    const totalStats = createEmptyCellStats();

    filteredPclStats.forEach(pcl => {
      const t = pcl.total;
      totalStats.target += t.target;
      totalStats.realisasi += t.realisasi;
      totalStats.open += t.open;
      totalStats.draft += t.draft;
      totalStats.submit += t.submit;
      totalStats.approve += t.approve;
      totalStats.reject += t.reject;
    });

    const completionRate = totalStats.target > 0 ? (totalStats.realisasi / totalStats.target) * 100 : 0;

    return {
      ...totalStats,
      completionRate
    };
  }, [filteredPclStats]);

  // Export functions to CSV
  const handleExportCSV = () => {
    let headers = ["Nama / Kode SLS", "Kecamatan", "Jabatan / Koseka"];
    
    // Add categories sub-headers
    categories.forEach(cat => {
      headers.push(
        `[${cat}] Target`,
        `[${cat}] Realisasi`,
        `[${cat}] Open`,
        `[${cat}] Submitted by Pencacah`,
        `[${cat}] Draft`,
        `[${cat}] Rejected by Pengawas`,
        `[${cat}] Approved by Pengawas`
      );
    });

    headers.push("Total Target", "Total Realisasi", "Total Open", "Total Submitted by Pencacah", "Total Draft", "Total Rejected by Pengawas", "Total Approved by Pengawas");

    const csvRows = [headers.join(",")];

    if (activeTab === "pcl") {
      filteredPclStats.forEach(pcl => {
        const row: (string | number)[] = [
          `"${pcl.nama}"`,
          `"${pcl.kec}"`,
          `"${pcl.jabatan}"`
        ];

        categories.forEach(cat => {
          const stats = pcl.categories[cat];
          row.push(
            stats.target,
            stats.realisasi,
            stats.open,
            stats.submit,
            stats.draft,
            stats.reject,
            stats.approve
          );
        });

        row.push(
          pcl.total.target,
          pcl.total.realisasi,
          pcl.total.open,
          pcl.total.submit,
          pcl.total.draft,
          pcl.total.reject,
          pcl.total.approve
        );

        csvRows.push(row.join(","));
      });
    } else if (activeTab === "pml") {
      filteredPmlStats.forEach(pml => {
        const row: (string | number)[] = [
          `"${pml.nama}"`,
          `"${pml.kec}"`,
          `"${pml.jabatan}"`
        ];

        categories.forEach(cat => {
          const stats = pml.categories[cat];
          row.push(
            stats.target,
            stats.realisasi,
            stats.open,
            stats.submit,
            stats.draft,
            stats.reject,
            stats.approve
          );
        });

        row.push(
          pml.total.target,
          pml.total.realisasi,
          pml.total.open,
          pml.total.submit,
          pml.total.draft,
          pml.total.reject,
          pml.total.approve
        );

        csvRows.push(row.join(","));
      });
    } else if (activeTab === "sls") {
      filteredSlsStats.forEach(sls => {
        const row: (string | number)[] = [
          `"${sls.slsCode}"`,
          `"${sls.kec}"`,
          `"${sls.koseka}"`
        ];

        categories.forEach(cat => {
          const stats = sls.categories[cat];
          row.push(
            stats.target,
            stats.realisasi,
            stats.open,
            stats.submit,
            stats.draft,
            stats.reject,
            stats.approve
          );
        });

        row.push(
          sls.total.target,
          sls.total.realisasi,
          sls.total.open,
          sls.total.submit,
          sls.total.draft,
          sls.total.reject,
          sls.total.approve
        );

        csvRows.push(row.join(","));
      });
    } else {
      kecamatanStats.forEach(kec => {
        const row: (string | number)[] = [
          `"${kec.kecName}"`,
          `"-"`,
          `"${kec.koseka}"`
        ];

        categories.forEach(cat => {
          const stats = kec.categories[cat];
          row.push(
            stats.target,
            stats.realisasi,
            stats.open,
            stats.submit,
            stats.draft,
            stats.reject,
            stats.approve
          );
        });

        row.push(
          kec.total.target,
          kec.total.realisasi,
          kec.total.open,
          kec.total.submit,
          kec.total.draft,
          kec.total.reject,
          kec.total.approve
        );

        csvRows.push(row.join(","));
      });
    }

    const csvBlob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(csvBlob);
    const link = document.createElement("a");
    const filename = activeTab === "pcl" 
      ? `tabulasi_pcl_monitoring_se2026_${Date.now()}.csv`
      : activeTab === "pml"
        ? `tabulasi_pml_monitoring_se2026_${Date.now()}.csv`
        : activeTab === "sls"
          ? `tabulasi_sls_monitoring_se2026_${Date.now()}.csv`
          : `tabulasi_kecamatan_monitoring_se2026_${Date.now()}.csv`;
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Render sub-cell content
  const CellContent = ({ stats, highlight }: { stats: CellStats; highlight?: boolean }) => {
    if (stats.target === 0) {
      return (
        <div className="text-center text-xs text-slate-400 dark:text-slate-600 font-mono py-4">
          -
        </div>
      );
    }

    return (
      <div className={`p-1.5 text-xs text-left font-mono rounded-lg transition-colors ${
        highlight 
          ? "bg-orange-500/10 dark:bg-orange-500/5 text-orange-950 dark:text-orange-200" 
          : "bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300"
      }`}>
        <div className="font-extrabold text-slate-900 dark:text-white flex justify-between border-b border-slate-200/50 dark:border-slate-800/50 pb-0.5 mb-1">
          <span>Target:</span>
          <span>{stats.target}</span>
        </div>
        <div className="font-extrabold text-emerald-600 dark:text-emerald-400 flex justify-between border-b border-slate-200/50 dark:border-slate-800/50 pb-0.5 mb-1">
          <span>Realisasi:</span>
          <span>{stats.realisasi}</span>
        </div>
        <div className="space-y-0.5 opacity-90 text-[10px] pl-1 font-semibold text-slate-500 dark:text-slate-400">
          <div className="flex justify-between">
            <span>1. Open</span>
            <span className="font-bold text-amber-500">{stats.open}</span>
          </div>
          <div className="flex justify-between">
            <span>2. Submitted by Pencacah</span>
            <span className="font-bold text-teal-500">{stats.submit}</span>
          </div>
          <div className="flex justify-between">
            <span>3. Draft</span>
            <span className="font-bold text-blue-500">{stats.draft}</span>
          </div>
          <div className="flex justify-between">
            <span>4. Rejected by Pengawas</span>
            <span className="font-bold text-red-500">{stats.reject}</span>
          </div>
          <div className="flex justify-between">
            <span>5. Approved by Pengawas</span>
            <span className="font-bold text-emerald-500">{stats.approve}</span>
          </div>
        </div>
      </div>
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
                className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-orange-500 text-white shadow-sm"
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
      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Banner Title */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-orange-600 to-amber-500 p-8 sm:p-10 text-white shadow-xl shadow-orange-600/10 mb-8">
          <div className="absolute right-0 top-0 w-80 h-80 rounded-full bg-white/10 blur-3xl translate-x-20 -translate-y-20"></div>
          <div className="absolute right-1/4 bottom-0 w-60 h-60 rounded-full bg-orange-400/20 blur-2xl translate-y-20"></div>
          
          <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div>
              <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-white/20 text-white mb-3 inline-block">
                Tabulasi & Kalkulasi Progres
              </span>
              <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight mb-2">
                Tabel Kalkulasi Progres Pendataan
              </h2>
              <p className="text-sm sm:text-lg text-orange-50 max-w-2xl font-light">
                Perhitungan real-time target dan realisasi status sampel per Petugas (PCL) dan Kecamatan di wilayah Kabupaten Kepulauan Sangihe.
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
              Mengekstrak dan Memproses Data Tabulasi BPS FASIH...
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
            {/* View Tabs */}
            <div className="flex border-b border-slate-200 dark:border-slate-800 mb-8">
              <button
                onClick={() => { setActiveTab("pcl"); setSelectedKec("all"); }}
                className={`py-4 px-6 font-bold text-sm border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === "pcl"
                    ? "border-orange-500 text-orange-500 dark:text-orange-400"
                    : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <User className="w-4 h-4" />
                Detail Petugas (PCL / PPL)
              </button>
              <button
                onClick={() => { setActiveTab("pml"); setSelectedKec("all"); }}
                className={`py-4 px-6 font-bold text-sm border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === "pml"
                    ? "border-orange-500 text-orange-500 dark:text-orange-400"
                    : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <SlidersHorizontal className="w-4 h-4" />
                Detail Pengawas (PML)
              </button>
              <button
                onClick={() => { setActiveTab("sls"); setSelectedKec("all"); }}
                className={`py-4 px-6 font-bold text-sm border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === "sls"
                    ? "border-orange-500 text-orange-500 dark:text-orange-400"
                    : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <Layers className="w-4 h-4" />
                Rekapitulasi SLS
              </button>
              <button
                onClick={() => { setActiveTab("kec"); setSelectedKec("all"); }}
                className={`py-4 px-6 font-bold text-sm border-b-2 transition-all flex items-center gap-2 ${
                  activeTab === "kec"
                    ? "border-orange-500 text-orange-500 dark:text-orange-400"
                    : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <Building className="w-4 h-4" />
                Ringkasan Wilayah (Kecamatan Overview)
              </button>
            </div>

            {/* Filter Section Card */}
            <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm mb-8">
              <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                
                {/* Left: Interactive Dropdown selectors */}
                <div className="flex flex-wrap gap-4 w-full md:w-auto items-center">
                  {(activeTab === "pcl" || activeTab === "pml" || activeTab === "sls") && (
                    <>
                      {/* Kecamatan Dropdown */}
                      <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold w-full sm:w-auto">
                        <MapPin className="w-4 h-4 text-orange-500" />
                        <select
                          value={selectedKec}
                          onChange={(e) => setSelectedKec(e.target.value)}
                          className="w-full sm:w-auto py-2.5 px-3.5 border border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 font-bold"
                        >
                          <option value="all">Semua Kecamatan</option>
                          {uniqueKecList.map((kec, idx) => (
                            <option key={idx} value={kec}>{kec}</option>
                          ))}
                        </select>
                      </div>

                      {/* PML Dropdown */}
                      {(activeTab === "pcl" || activeTab === "pml") && (
                        <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold w-full sm:w-auto">
                          <SlidersHorizontal className="w-4 h-4 text-orange-500" />
                          <select
                            value={selectedPml}
                            onChange={(e) => handlePmlChange(e.target.value)}
                            className="w-full sm:w-auto py-2.5 px-3.5 border border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 font-bold"
                          >
                            <option value="all">Semua PML (Pengawas)</option>
                            {pmlList.map((pml, idx) => (
                              <option key={idx} value={pml.nama_petugas}>{pml.nama_petugas}</option>
                            ))}
                          </select>
                        </div>
                      )}
                    </>
                  )}

                  {/* Search Input */}
                  {(activeTab === "pcl" || activeTab === "pml" || activeTab === "sls") && (
                    <div className="relative w-full sm:w-64">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        type="text"
                        placeholder={
                          activeTab === "pcl" 
                            ? "Cari nama PCL..." 
                            : activeTab === "pml" 
                              ? "Cari nama PML..." 
                              : "Cari SLS / Kecamatan..."
                        }
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-9 pr-9 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-xs focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all font-semibold"
                      />
                      {searchQuery && (
                        <button
                          onClick={() => setSearchQuery("")}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-400 transition-colors"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Right: Export button */}
                <div className="w-full md:w-auto flex justify-end">
                  <button
                    onClick={handleExportCSV}
                    className="w-full sm:w-auto py-2.5 px-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors flex items-center justify-center gap-1.5 text-xs font-bold bg-white dark:bg-slate-950 cursor-pointer shadow-sm"
                  >
                    <Download className="w-4 h-4 text-orange-500" />
                    <span>Ekspor CSV</span>
                  </button>
                </div>

              </div>

              {/* Progress Summary Cards */}
              {activeTab === "pcl" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-100 dark:border-slate-800">
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total PCL Tampil</span>
                    <span className="text-xl font-extrabold text-slate-900 dark:text-white mt-1 block">{filteredPclStats.length} petugas</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total Beban Target</span>
                    <span className="text-xl font-extrabold text-slate-900 dark:text-white mt-1 block">{selectedOverviewStats.target.toLocaleString("id-ID")}</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total Realisasi</span>
                    <span className="text-xl font-extrabold text-emerald-500 mt-1 block">{selectedOverviewStats.realisasi.toLocaleString("id-ID")}</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Persentase Selesai</span>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-2xl font-black text-orange-500">{selectedOverviewStats.completionRate.toFixed(2)}%</span>
                      <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-orange-500 h-full rounded-full" style={{ width: `${selectedOverviewStats.completionRate}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "pml" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-100 dark:border-slate-800">
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total PML Tampil</span>
                    <span className="text-xl font-extrabold text-slate-900 dark:text-white mt-1 block">{filteredPmlStats.length} pengawas</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total Beban Target</span>
                    <span className="text-xl font-extrabold text-slate-900 dark:text-white mt-1 block">{selectedPmlOverviewStats.target.toLocaleString("id-ID")}</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total Realisasi</span>
                    <span className="text-xl font-extrabold text-emerald-500 mt-1 block">{selectedPmlOverviewStats.realisasi.toLocaleString("id-ID")}</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Persentase Selesai</span>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-2xl font-black text-orange-500">{selectedPmlOverviewStats.completionRate.toFixed(2)}%</span>
                      <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-orange-500 h-full rounded-full" style={{ width: `${selectedPmlOverviewStats.completionRate}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "sls" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-100 dark:border-slate-800">
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total SLS Tampil</span>
                    <span className="text-xl font-extrabold text-slate-900 dark:text-white mt-1 block">{filteredSlsStats.length} SLS</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total Beban Target</span>
                    <span className="text-xl font-extrabold text-slate-900 dark:text-white mt-1 block">{selectedSlsOverviewStats.target.toLocaleString("id-ID")}</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Total Realisasi</span>
                    <span className="text-xl font-extrabold text-emerald-500 mt-1 block">{selectedSlsOverviewStats.realisasi.toLocaleString("id-ID")}</span>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-950/50 p-4 rounded-xl border border-slate-100 dark:border-slate-900/50">
                    <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Persentase Selesai</span>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-2xl font-black text-orange-500">{selectedSlsOverviewStats.completionRate.toFixed(2)}%</span>
                      <div className="flex-1 bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-orange-500 h-full rounded-full" style={{ width: `${selectedSlsOverviewStats.completionRate}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Content Table Card */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-lg overflow-hidden">
              {/* Top scrollbar synced with table */}
              <div 
                ref={topScrollRef}
                onScroll={handleTopScroll}
                className="overflow-x-auto overflow-y-hidden w-full bg-slate-50/30 dark:bg-slate-900/30 border-b border-slate-200 dark:border-slate-800"
                style={{ height: "10px" }}
              >
                <div style={{ width: `${tableWidth}px`, height: "10px" }} />
              </div>

              <div 
                ref={tableContainerRef}
                onScroll={handleTableScroll}
                className="overflow-auto max-h-[700px] w-full"
              >
                
                {activeTab === "pcl" ? (
                  // =================== TABLE 1: DETAIL PCL ===================
                  <table className="w-full border-collapse border border-slate-200 dark:border-slate-800 min-w-[1200px]">
                    <thead className="sticky top-0 z-20 bg-slate-50 dark:bg-slate-900 shadow-[0_1px_0_0_rgba(226,232,240,1)] dark:shadow-[0_1px_0_0_rgba(30,41,59,1)]">
                      {/* Top Header Row */}
                      <tr className="bg-orange-100/80 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200 border-b border-slate-200 dark:border-slate-700 text-center">
                        <th rowSpan={2} className="px-4 py-4 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold text-left w-56 sticky left-0 bg-orange-100 dark:bg-slate-800 z-30">
                          Nama PCL
                        </th>
                        <th colSpan={7} className="py-2 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold tracking-wide uppercase">
                          Skala Prelist
                        </th>
                        <th rowSpan={2} className="px-4 py-4 text-sm font-extrabold uppercase">
                          Total
                        </th>
                      </tr>
                      {/* Sub Header Row */}
                      <tr className="bg-slate-100/90 dark:bg-slate-800/40 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 text-center text-xs font-bold">
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">Keluarga</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMK</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM Bangunan Lain</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UM</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UB</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Dummy</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Keluarga</th>
                      </tr>
                    </thead>
                    
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {filteredPclStats.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="px-4 py-16 text-center text-slate-400 font-medium text-sm">
                            Tidak ada data PCL ditemukan untuk filter ini.
                          </td>
                        </tr>
                      ) : (
                        filteredPclStats.map((pcl, idx) => (
                          <tr 
                            key={idx} 
                            className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-all border-b border-slate-100 dark:border-slate-800"
                          >
                            {/* PCL Name cell */}
                            <td className="px-4 py-3 border-r border-slate-200 dark:border-slate-800 font-bold text-slate-950 dark:text-white sticky left-0 bg-white dark:bg-slate-900 z-10 shadow-[2px_0_5px_rgba(0,0,0,0.05)]">
                              <div>{pcl.nama}</div>
                              <div className="text-[10px] text-slate-400 font-normal mt-0.5">{pcl.kec}</div>
                            </td>

                            {/* Category cells */}
                            {categories.map((cat, cIdx) => (
                              <td key={cIdx} className="p-2 border-r border-slate-200 dark:border-slate-800 align-top">
                                <CellContent stats={pcl.categories[cat]} />
                              </td>
                            ))}

                            {/* Total cell */}
                            <td className="p-2 align-top bg-orange-500/5 dark:bg-orange-500/0">
                              <CellContent stats={pcl.total} highlight={true} />
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                ) : activeTab === "pml" ? (
                  // =================== TABLE 3: DETAIL PML ===================
                  <table className="w-full border-collapse border border-slate-200 dark:border-slate-800 min-w-[1200px]">
                    <thead className="sticky top-0 z-20 bg-slate-50 dark:bg-slate-900 shadow-[0_1px_0_0_rgba(226,232,240,1)] dark:shadow-[0_1px_0_0_rgba(30,41,59,1)]">
                      {/* Top Header Row */}
                      <tr className="bg-orange-100/80 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200 border-b border-slate-200 dark:border-slate-700 text-center">
                        <th rowSpan={2} className="px-4 py-4 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold text-left w-56 sticky left-0 bg-orange-100 dark:bg-slate-800 z-30">
                          Nama PML (Pengawas)
                        </th>
                        <th colSpan={7} className="py-2 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold tracking-wide uppercase">
                          Skala Prelist
                        </th>
                        <th rowSpan={2} className="px-4 py-4 text-sm font-extrabold uppercase">
                          Total
                        </th>
                      </tr>
                      {/* Sub Header Row */}
                      <tr className="bg-slate-100/90 dark:bg-slate-800/40 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 text-center text-xs font-bold">
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">Keluarga</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMK</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM Bangunan Lain</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UM</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UB</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Dummy</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Keluarga</th>
                      </tr>
                    </thead>
                    
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {filteredPmlStats.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="px-4 py-16 text-center text-slate-400 font-medium text-sm">
                            Tidak ada data PML ditemukan untuk filter ini.
                          </td>
                        </tr>
                      ) : (
                        filteredPmlStats.map((pml, idx) => (
                          <tr 
                            key={idx} 
                            className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-all border-b border-slate-100 dark:border-slate-800"
                          >
                            {/* PML Name cell */}
                            <td className="px-4 py-3 border-r border-slate-200 dark:border-slate-800 font-bold text-slate-950 dark:text-white sticky left-0 bg-white dark:bg-slate-900 z-10 shadow-[2px_0_5px_rgba(0,0,0,0.05)]">
                              <div>{pml.nama}</div>
                              <div className="text-[10px] text-slate-400 font-normal mt-0.5">{pml.kec}</div>
                            </td>

                            {/* Category cells */}
                            {categories.map((cat, cIdx) => (
                              <td key={cIdx} className="p-2 border-r border-slate-200 dark:border-slate-800 align-top">
                                <CellContent stats={pml.categories[cat]} />
                              </td>
                            ))}

                            {/* Total cell */}
                            <td className="p-2 align-top bg-orange-500/5 dark:bg-orange-500/0">
                              <CellContent stats={pml.total} highlight={true} />
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                ) : activeTab === "sls" ? (
                  // =================== TABLE 4: DETAIL SLS ===================
                  <>
                    <table className="w-full border-collapse border border-slate-200 dark:border-slate-800 min-w-[1200px]">
                      <thead className="sticky top-0 z-20 bg-slate-50 dark:bg-slate-900 shadow-[0_1px_0_0_rgba(226,232,240,1)] dark:shadow-[0_1px_0_0_rgba(30,41,59,1)]">
                        {/* Top Header Row */}
                        <tr className="bg-orange-100/80 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200 border-b border-slate-200 dark:border-slate-700 text-center">
                          <th rowSpan={2} className="px-4 py-4 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold text-left w-56 sticky left-0 bg-orange-100 dark:bg-slate-800 z-30">
                            Kode SLS (14 Digit)
                          </th>
                          <th colSpan={7} className="py-2 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold tracking-wide uppercase">
                            Skala Prelist
                          </th>
                          <th rowSpan={2} className="px-4 py-4 text-sm font-extrabold uppercase">
                            Total
                          </th>
                        </tr>
                        {/* Sub Header Row */}
                        <tr className="bg-slate-100/90 dark:bg-slate-800/40 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 text-center text-xs font-bold">
                          <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">Keluarga</th>
                          <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMK</th>
                          <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM Bangunan Lain</th>
                          <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UM</th>
                          <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UB</th>
                          <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Dummy</th>
                          <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Keluarga</th>
                        </tr>
                      </thead>
                      
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                        {paginatedSlsStats.length === 0 ? (
                          <tr>
                            <td colSpan={9} className="px-4 py-16 text-center text-slate-400 font-medium text-sm">
                              Tidak ada data SLS ditemukan untuk filter ini.
                            </td>
                          </tr>
                        ) : (
                          paginatedSlsStats.map((sls, idx) => (
                            <tr 
                              key={idx} 
                              className={`hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-all border-b border-slate-100 dark:border-slate-800 ${
                                sls.isPrioritas 
                                  ? "bg-orange-500/5 hover:bg-orange-500/10 dark:bg-orange-500/5 dark:hover:bg-orange-500/10" 
                                  : ""
                              }`}
                            >
                              {/* SLS Code cell */}
                              <td className={`px-4 py-3 border-r border-slate-200 dark:border-slate-800 font-bold sticky left-0 z-10 shadow-[2px_0_5px_rgba(0,0,0,0.05)] ${
                                sls.isPrioritas
                                  ? "bg-orange-50/90 dark:bg-orange-950/20 text-orange-900 dark:text-orange-300 border-l-2 border-l-orange-500"
                                  : "bg-white dark:bg-slate-900 text-slate-950 dark:text-white border-l-2 border-l-transparent"
                              }`}>
                                <div className="flex items-center gap-1.5">
                                  <span className="font-mono text-sm tracking-wider">{sls.slsCode}</span>
                                  {sls.isPrioritas && (
                                    <span className="inline-flex px-1.5 py-0.5 rounded text-[8px] font-extrabold uppercase bg-orange-500 text-white dark:bg-orange-600 tracking-wider">
                                      Prioritas
                                    </span>
                                  )}
                                </div>
                                <div className="text-[10px] text-slate-400 font-normal mt-0.5">{sls.kec} • Koseka: {sls.koseka}</div>
                              </td>

                              {/* Category cells */}
                              {categories.map((cat, cIdx) => (
                                <td key={cIdx} className="p-2 border-r border-slate-200 dark:border-slate-800 align-top">
                                  <CellContent stats={sls.categories[cat]} />
                                </td>
                              ))}

                              {/* Total cell */}
                              <td className="p-2 align-top bg-orange-500/5 dark:bg-orange-500/0">
                                <CellContent stats={sls.total} highlight={true} />
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>

                    {/* Pagination Controls */}
                    {filteredSlsStats.length > 0 && (
                      <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                        <div className="text-xs text-slate-500 dark:text-slate-400 font-semibold">
                          Menampilkan <span className="font-bold text-slate-900 dark:text-white">{Math.min((slsPage - 1) * slsPerPage + 1, filteredSlsStats.length)}</span> - <span className="font-bold text-slate-900 dark:text-white">{Math.min(slsPage * slsPerPage, filteredSlsStats.length)}</span> dari <span className="font-bold text-slate-900 dark:text-white">{filteredSlsStats.length}</span> SLS
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setSlsPage(prev => Math.max(prev - 1, 1))}
                            disabled={slsPage === 1}
                            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-bold transition-all hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent"
                          >
                            Sebelumnya
                          </button>
                          {Array.from({ length: Math.min(5, totalSlsPages) }, (_, i) => {
                            let pageNum = slsPage;
                            if (slsPage <= 3) {
                              pageNum = i + 1;
                            } else if (slsPage >= totalSlsPages - 2) {
                              pageNum = totalSlsPages - 4 + i;
                            } else {
                              pageNum = slsPage - 2 + i;
                            }
                            if (pageNum < 1 || pageNum > totalSlsPages) return null;

                            return (
                              <button
                                key={pageNum}
                                onClick={() => setSlsPage(pageNum)}
                                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                                  slsPage === pageNum
                                    ? "bg-orange-500 text-white shadow-sm"
                                    : "border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800"
                                }`}
                              >
                                {pageNum}
                              </button>
                            );
                          })}
                          <button
                            onClick={() => setSlsPage(prev => Math.min(prev + 1, totalSlsPages))}
                            disabled={slsPage === totalSlsPages}
                            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-bold transition-all hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent"
                          >
                            Selanjutnya
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  // =================== TABLE 2: KECAMATAN OVERVIEW ===================
                  <table className="w-full border-collapse border border-slate-200 dark:border-slate-800 min-w-[1200px]">
                    <thead className="sticky top-0 z-20 bg-slate-50 dark:bg-slate-900 shadow-[0_1px_0_0_rgba(226,232,240,1)] dark:shadow-[0_1px_0_0_rgba(30,41,59,1)]">
                      {/* Top Header Row */}
                      <tr className="bg-orange-100/80 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200 border-b border-slate-200 dark:border-slate-700 text-center">
                        <th rowSpan={2} className="px-4 py-4 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold text-left w-56 sticky left-0 bg-orange-100 dark:bg-slate-800 z-30">
                          Nama Kecamatan
                        </th>
                        <th colSpan={7} className="py-2 border-r border-slate-200 dark:border-slate-700 text-sm font-extrabold tracking-wide uppercase">
                          Skala Prelist
                        </th>
                        <th rowSpan={2} className="px-4 py-4 text-sm font-extrabold uppercase">
                          Total
                        </th>
                      </tr>
                      {/* Sub Header Row */}
                      <tr className="bg-slate-100/90 dark:bg-slate-800/40 text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 text-center text-xs font-bold">
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">Keluarga</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMK</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM Bangunan Lain</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UM</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UB</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Dummy</th>
                        <th className="px-2 py-2.5 border-r border-slate-200 dark:border-slate-700 w-36">UMKM/Keluarga</th>
                      </tr>
                    </thead>
                    
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {kecamatanStats.map((kec, idx) => (
                        <tr 
                          key={idx} 
                          className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-all border-b border-slate-100 dark:border-slate-800"
                        >
                          {/* Kecamatan Name cell */}
                          <td className="px-4 py-3 border-r border-slate-200 dark:border-slate-800 font-bold text-slate-950 dark:text-white sticky left-0 bg-white dark:bg-slate-900 z-10 shadow-[2px_0_5px_rgba(0,0,0,0.05)]">
                            <div>{kec.kecName}</div>
                            <div className="text-[10px] text-slate-400 font-normal mt-0.5">Koseka: {kec.koseka}</div>
                          </td>

                          {/* Category cells */}
                          {categories.map((cat, cIdx) => (
                            <td key={cIdx} className="p-2 border-r border-slate-200 dark:border-slate-800 align-top">
                              <CellContent stats={kec.categories[cat]} />
                            </td>
                          ))}

                          {/* Total cell */}
                          <td className="p-2 align-top bg-orange-500/5 dark:bg-orange-500/0">
                            <CellContent stats={kec.total} highlight={true} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

              </div>
            </div>
          </>
        )}

      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-6 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>© 2026 Badan Pusat Statistik (BPS) Kabupaten Kepulauan Sangihe. Hak Cipta Dilindungi.</p>
          <p>
            Pengembang:{" "}
            <a
              href="http://hamdani-portfolio.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold text-orange-500 hover:text-orange-600 dark:hover:text-orange-400 transition-colors"
            >
              Hamdani
            </a>
          </p>
        </div>
      </footer>

    </div>
  );
}
