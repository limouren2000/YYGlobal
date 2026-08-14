"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, Profile, ProgramRecommendation } from "@/lib/api";

const STORAGE_KEY = "yyglobal-program-recommendations-v1";

type StoredSession = {
  profileVersion: string;
  query: string;
  items: ProgramRecommendation[];
  latestBatchIds: string[];
  selectedIds: string[];
};

type BatchRequest = {
  query: string;
  excludedIds: string[];
  profileVersion: string;
  replace: boolean;
};

type RecommendationContextValue = {
  profile?: Profile;
  profileReady: boolean;
  input: string;
  setInput: (value: string) => void;
  queryText: string;
  items: ProgramRecommendation[];
  latestBatchIds: string[];
  selected: string[];
  setSelected: React.Dispatch<React.SetStateAction<string[]>>;
  recommendationNotice: string;
  isPending: boolean;
  error: Error | null;
  profileChoiceOpen: boolean;
  requestBatch: (replace: boolean, query?: string) => void;
  restartForChangedProfile: () => void;
  appendForChangedProfile: () => void;
  dismissProfileChoice: () => void;
};

const RecommendationContext = createContext<RecommendationContextValue | null>(null);

export function RecommendationProvider({ children }: { children: React.ReactNode }) {
  const initialRequestStarted = useRef(false);
  const [hydrated, setHydrated] = useState(false);
  const [input, setInput] = useState("");
  const [queryText, setQueryText] = useState("");
  const [items, setItems] = useState<ProgramRecommendation[]>([]);
  const [latestBatchIds, setLatestBatchIds] = useState<string[]>([]);
  const [sessionProfileVersion, setSessionProfileVersion] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [recommendationNotice, setRecommendationNotice] = useState("");
  const [profileChoiceOpen, setProfileChoiceOpen] = useState(false);
  const [dismissedProfileVersion, setDismissedProfileVersion] = useState("");
  const profileQuery = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const profile = profileQuery.data;
  const profileReady = Boolean(profile?.confirmed && profile.target_fields.length && profile.target_countries.length);

  const fetchBatch = useMutation({
    mutationFn: (request: BatchRequest) => api.programRecommendations(request.query, request.excludedIds),
    onMutate: () => setRecommendationNotice(""),
    onSuccess: (batch, request) => {
      const freshIds = new Set(batch.map((item) => item.program.id));
      setItems((current) => request.replace ? batch : [...batch, ...current.filter((item) => !freshIds.has(item.program.id))]);
      setLatestBatchIds(batch.map((item) => item.program.id));
      setSessionProfileVersion(request.profileVersion);
      setQueryText(request.query);
      setInput(request.query);
      setRecommendationNotice(batch.length === 5 ? `已在页面顶部新增 ${batch.length} 个项目。` : batch.length ? `已新增 ${batch.length} 个项目，当前条件下没有更多项目了。` : "当前条件下暂时没有更多未展示的项目。");
    },
    onError: (error) => setRecommendationNotice(error instanceof Error ? error.message : "推荐失败"),
  });

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const stored = JSON.parse(raw) as Partial<StoredSession>;
        setItems(Array.isArray(stored.items) ? stored.items : []);
        setLatestBatchIds(Array.isArray(stored.latestBatchIds) ? stored.latestBatchIds : []);
        setSelected(Array.isArray(stored.selectedIds) ? stored.selectedIds : []);
        setSessionProfileVersion(stored.profileVersion ?? "");
        setQueryText(stored.query ?? "");
        setInput(stored.query ?? "");
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      profileVersion: sessionProfileVersion,
      query: queryText,
      items,
      latestBatchIds,
      selectedIds: selected,
    } satisfies StoredSession));
  }, [hydrated, items, latestBatchIds, queryText, selected, sessionProfileVersion]);

  useEffect(() => {
    const currentVersion = profile?.updated_at;
    if (!hydrated || !currentVersion || !items.length || !sessionProfileVersion) return;
    if (currentVersion !== sessionProfileVersion && currentVersion !== dismissedProfileVersion) setProfileChoiceOpen(true);
  }, [dismissedProfileVersion, hydrated, items.length, profile?.updated_at, sessionProfileVersion]);

  useEffect(() => {
    if (!hydrated || !profileReady || items.length || initialRequestStarted.current || !profile?.updated_at) return;
    initialRequestStarted.current = true;
    fetchBatch.mutate({ query: "", excludedIds: [], profileVersion: profile.updated_at, replace: true });
  }, [fetchBatch, hydrated, items.length, profile?.updated_at, profileReady]);

  const requestBatch = (replace: boolean, query = queryText) => {
    const profileVersion = profile?.updated_at ?? sessionProfileVersion;
    if (!profileVersion || fetchBatch.isPending) return;
    initialRequestStarted.current = true;
    fetchBatch.mutate({ query, excludedIds: replace ? [] : items.map((item) => item.program.id), profileVersion, replace });
  };

  const restartForChangedProfile = () => {
    if (!profile?.updated_at || fetchBatch.isPending) return;
    initialRequestStarted.current = true;
    setProfileChoiceOpen(false);
    setDismissedProfileVersion(profile.updated_at);
    setItems([]);
    setLatestBatchIds([]);
    setSelected([]);
    setQueryText("");
    setInput("");
    fetchBatch.mutate({ query: "", excludedIds: [], profileVersion: profile.updated_at, replace: true });
  };

  const appendForChangedProfile = () => {
    if (!profile?.updated_at || fetchBatch.isPending) return;
    initialRequestStarted.current = true;
    setProfileChoiceOpen(false);
    setDismissedProfileVersion(profile.updated_at);
    fetchBatch.mutate({ query: "", excludedIds: items.map((item) => item.program.id), profileVersion: profile.updated_at, replace: false });
  };

  const dismissProfileChoice = () => {
    if (profile?.updated_at) setDismissedProfileVersion(profile.updated_at);
    setProfileChoiceOpen(false);
  };

  return <RecommendationContext.Provider value={{
    profile, profileReady, input, setInput, queryText, items, latestBatchIds,
    selected, setSelected, recommendationNotice, isPending: fetchBatch.isPending,
    error: fetchBatch.error instanceof Error ? fetchBatch.error : null,
    profileChoiceOpen, requestBatch, restartForChangedProfile,
    appendForChangedProfile, dismissProfileChoice,
  }}>{children}</RecommendationContext.Provider>;
}

export function useRecommendations() {
  const context = useContext(RecommendationContext);
  if (!context) throw new Error("useRecommendations must be used within RecommendationProvider");
  return context;
}
