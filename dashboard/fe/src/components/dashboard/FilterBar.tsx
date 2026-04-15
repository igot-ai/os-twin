'use client';

import { useState, useEffect, useRef } from 'react';
import { PlanStatus, Domain } from '@/types';

export type SortOption = 'newest' | 'oldest' | 'progress-high' | 'progress-low' | 'alphabetical';

interface FilterBarProps {
  onSearchChange: (search: string) => void;
  onStatusChange: (statuses: PlanStatus[]) => void;
  onDomainChange: (domains: Domain[]) => void;
  onSortChange: (sort: SortOption) => void;
  onViewChange: (view: 'grid' | 'table') => void;
  currentView: 'grid' | 'table';
  availableDomains: Domain[];
  availableStatuses: PlanStatus[];
}

export default function FilterBar({
  onSearchChange,
  onStatusChange,
  onDomainChange,
  onSortChange,
  onViewChange,
  currentView,
  availableDomains,
  availableStatuses
}: FilterBarProps) {
  const [search, setSearch] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState<PlanStatus[]>([]);
  const [selectedDomains, setSelectedDomains] = useState<Domain[]>([]);
  const [currentSort, setCurrentSort] = useState<SortOption>('newest');

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      onSearchChange(search);
    }, 200);

    return () => clearTimeout(handler);
  }, [search, onSearchChange]);

  const toggleStatus = (status: PlanStatus) => {
    const next = selectedStatuses.includes(status)
      ? selectedStatuses.filter(s => s !== status)
      : [...selectedStatuses, status];
    setSelectedStatuses(next);
    onStatusChange(next);
  };

  const toggleDomain = (domain: Domain) => {
    const next = selectedDomains.includes(domain)
      ? selectedDomains.filter(d => d !== domain)
      : [...selectedDomains, domain];
    setSelectedDomains(next);
    onDomainChange(next);
  };

  const handleSort = (sort: SortOption) => {
    setCurrentSort(sort);
    onSortChange(sort);
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 py-4 px-1">
      <div className="flex flex-1 items-center gap-3 min-w-[300px]">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-faint text-lg">
            search
          </span>
          <input
            type="text"
            placeholder="Search plans..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
          />
        </div>

        {/* Status Filter */}
        <FilterDropdown
          label="Status"
          options={availableStatuses}
          selected={selectedStatuses}
          onToggle={toggleStatus}
          icon="filter_list"
        />

        {/* Domain Filter */}
        <FilterDropdown
          label="Domain"
          options={availableDomains}
          selected={selectedDomains}
          onToggle={toggleDomain}
          icon="category"
        />
      </div>

      <div className="flex items-center gap-2">
        {/* Sort */}
        <div className="flex items-center gap-2 text-xs font-semibold text-text-muted mr-2">
          <span>Sort:</span>
          <select
            value={currentSort}
            onChange={(e) => handleSort(e.target.value as SortOption)}
            className="bg-transparent border-none focus:ring-0 cursor-pointer text-text-main hover:text-primary"
          >
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="progress-high">Highest Progress</option>
            <option value="progress-low">Lowest Progress</option>
            <option value="alphabetical">A-Z</option>
          </select>
        </div>

        <div className="h-6 w-px bg-border mx-1" />

        {/* View Toggle */}
        <div className="flex items-center bg-surface border border-border rounded-lg p-0.5">
          <button
            onClick={() => onViewChange('grid')}
            className={`p-1.5 rounded-md transition-all ${
              currentView === 'grid' 
                ? 'bg-surface-hover text-primary shadow-sm' 
                : 'text-text-faint hover:text-text-muted'
            }`}
            title="Grid View"
          >
            <span className="material-symbols-outlined text-xl leading-none">grid_view</span>
          </button>
          <button
            onClick={() => onViewChange('table')}
            className={`p-1.5 rounded-md transition-all ${
              currentView === 'table' 
                ? 'bg-surface-hover text-primary shadow-sm' 
                : 'text-text-faint hover:text-text-muted'
            }`}
            title="Table View"
          >
            <span className="material-symbols-outlined text-xl leading-none">view_list</span>
          </button>
        </div>
      </div>
    </div>
  );
}

interface FilterDropdownProps<T> {
  label: string;
  options: T[];
  selected: T[];
  onToggle: (option: T) => void;
  icon: string;
}

function FilterDropdown<T extends string>({ 
  label, 
  options, 
  selected, 
  onToggle, 
  icon 
}: FilterDropdownProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border transition-all ${
          selected.length > 0 
            ? 'bg-primary-muted border-primary text-primary' 
            : 'bg-surface border-border text-text-muted hover:border-text-faint hover:text-text-main'
        }`}
      >
        <span className="material-symbols-outlined text-lg">{icon}</span>
        {label}
        {selected.length > 0 && (
          <span className="flex items-center justify-center w-5 h-5 ml-1 text-[10px] font-bold bg-primary text-white rounded-full">
            {selected.length}
          </span>
        )}
        <span className="material-symbols-outlined text-lg leading-none ml-1">
          {isOpen ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {isOpen && (
        <div className="absolute left-0 z-50 mt-2 w-56 p-2 origin-top-left rounded-xl bg-surface shadow-modal border border-border animate-in zoom-in-95 duration-100">
          <div className="max-h-60 overflow-y-auto">
            {options.map((option) => (
              <label
                key={option}
                className="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer hover:bg-surface-hover transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(option)}
                  onChange={() => onToggle(option)}
                  className="w-4 h-4 rounded text-primary focus:ring-primary border-border"
                />
                <span className="text-sm font-medium text-text-main capitalize">
                  {option}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
