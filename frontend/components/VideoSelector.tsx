'use client'

import { useState, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { 
  CheckSquare, 
  Square, 
  Search, 
  Play, 
  Clock, 
  Eye,
  Filter,
  SortAsc,
  Users,
  Video
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDuration, type BulkAnalyzeResponse } from '@/services/bulkApi'

interface VideoSelectorProps {
  analysis: BulkAnalyzeResponse
  selectedVideos: string[]
  onSelectionChange: (selectedVideoIds: string[]) => void
  disabled?: boolean
}

type SortBy = 'order' | 'title' | 'duration' | 'duration_desc'

export function VideoSelector({ 
  analysis, 
  selectedVideos, 
  onSelectionChange,
  disabled = false 
}: VideoSelectorProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('order')
  const [showFilters, setShowFilters] = useState(false)

  // Filter and sort videos based on search term and sort option
  const filteredAndSortedVideos = useMemo(() => {
    const filtered = analysis.videos.filter(video =>
      video.title.toLowerCase().includes(searchTerm.toLowerCase())
    )

    switch (sortBy) {
      case 'title':
        filtered.sort((a, b) => a.title.localeCompare(b.title))
        break
      case 'duration':
        filtered.sort((a, b) => a.duration - b.duration)
        break
      case 'duration_desc':
        filtered.sort((a, b) => b.duration - a.duration)
        break
      case 'order':
      default:
        // Keep original order
        break
    }

    return filtered
  }, [analysis.videos, searchTerm, sortBy])

  // Calculate selection stats
  const selectionStats = useMemo(() => {
    const selectedCount = selectedVideos.length
    const totalDuration = selectedVideos.reduce((acc, videoId) => {
      const video = analysis.videos.find(v => v.video_id === videoId)
      return acc + (video?.duration || 0)
    }, 0)
    
    return {
      count: selectedCount,
      totalDuration,
      estimatedHours: totalDuration / 3600
    }
  }, [selectedVideos, analysis.videos])

  const handleVideoToggle = useCallback((videoId: string) => {
    if (disabled) return
    
    const isSelected = selectedVideos.includes(videoId)
    if (isSelected) {
      onSelectionChange(selectedVideos.filter(id => id !== videoId))
    } else {
      onSelectionChange([...selectedVideos, videoId])
    }
  }, [selectedVideos, onSelectionChange, disabled])

  const handleSelectAll = useCallback(() => {
    if (disabled) return
    
    const allVideoIds = filteredAndSortedVideos.map(v => v.video_id)
    onSelectionChange(allVideoIds)
  }, [filteredAndSortedVideos, onSelectionChange, disabled])

  const handleSelectNone = useCallback(() => {
    if (disabled) return
    onSelectionChange([])
  }, [onSelectionChange, disabled])

  const handleSelectFiltered = useCallback(() => {
    if (disabled) return
    
    const filteredVideoIds = filteredAndSortedVideos.map(v => v.video_id)
    const newSelection = [...new Set([...selectedVideos, ...filteredVideoIds])]
    onSelectionChange(newSelection)
  }, [filteredAndSortedVideos, selectedVideos, onSelectionChange, disabled])

  return (
    <Card className="w-full max-w-6xl mx-auto bg-gradient-to-b from-card to-card/95 border-border/50 shadow-lg">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-semibold text-foreground flex items-center gap-2">
              {analysis.source_type === 'playlist' ? (
                <Play className="h-5 w-5 text-primary" />
              ) : (
                <Users className="h-5 w-5 text-primary" />
              )}
              Select Videos to Transcribe
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Found {analysis.total_videos} videos in {analysis.title}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {selectionStats.count} selected
            </Badge>
            {selectionStats.count > 0 && (
              <Badge variant="outline" className="text-xs">
                ~{selectionStats.estimatedHours.toFixed(1)}h total
              </Badge>
            )}
          </div>
        </div>

        {/* Tier Limits Warning */}
        {!analysis.can_process_all && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-r from-orange-500/10 to-yellow-500/10 border border-orange-500/20 rounded-xl p-4"
          >
            <div className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-orange-500 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-white text-xs font-bold">!</span>
              </div>
              <div>
                <h4 className="font-medium text-foreground">Tier Limit Notice</h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Your current tier allows processing up to {analysis.tier_limits.max_videos_per_job} videos per job. 
                  Found {analysis.total_videos} videos total.
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* Search and Controls */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search videos..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 bg-background/50 border-border/50"
              disabled={disabled}
            />
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className="shrink-0"
              disabled={disabled}
            >
              <Filter className="h-4 w-4 mr-1" />
              {showFilters ? 'Hide' : 'Show'} Filters
            </Button>
          </div>
        </div>

        {/* Filters Row */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="flex flex-wrap items-center gap-4 p-4 bg-muted/30 rounded-lg"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Sort by:</span>
                <Button
                  variant={sortBy === 'order' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSortBy('order')}
                  disabled={disabled}
                >
                  Original Order
                </Button>
                <Button
                  variant={sortBy === 'title' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSortBy('title')}
                  disabled={disabled}
                >
                  <SortAsc className="h-3 w-3 mr-1" />
                  Title
                </Button>
                <Button
                  variant={sortBy === 'duration' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSortBy('duration')}
                  disabled={disabled}
                >
                  <Clock className="h-3 w-3 mr-1" />
                  Duration ↑
                </Button>
                <Button
                  variant={sortBy === 'duration_desc' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSortBy('duration_desc')}
                  disabled={disabled}
                >
                  <Clock className="h-3 w-3 mr-1" />
                  Duration ↓
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Selection Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleSelectAll}
            disabled={disabled || filteredAndSortedVideos.length === 0}
          >
            <CheckSquare className="h-4 w-4 mr-1" />
            Select All ({filteredAndSortedVideos.length})
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSelectNone}
            disabled={disabled || selectedVideos.length === 0}
          >
            <Square className="h-4 w-4 mr-1" />
            Select None
          </Button>
          {searchTerm && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSelectFiltered}
              disabled={disabled || filteredAndSortedVideos.length === 0}
            >
              <Search className="h-4 w-4 mr-1" />
              Select Filtered ({filteredAndSortedVideos.length})
            </Button>
          )}
        </div>

        {/* Video List */}
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {filteredAndSortedVideos.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchTerm ? 'No videos match your search.' : 'No videos to display.'}
            </div>
          ) : (
            <AnimatePresence mode="popLayout">
              {filteredAndSortedVideos.map((video, index) => {
                const isSelected = selectedVideos.includes(video.video_id)
                
                return (
                  <motion.div
                    key={video.video_id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ delay: index * 0.02 }}
                    className={cn(
                      "flex items-center gap-4 p-4 rounded-lg border transition-all duration-200 cursor-pointer group",
                      isSelected 
                        ? "bg-primary/10 border-primary/30 shadow-md" 
                        : "bg-background/50 border-border/50 hover:bg-muted/30 hover:border-border",
                      disabled && "opacity-50 cursor-not-allowed"
                    )}
                    onClick={() => handleVideoToggle(video.video_id)}
                  >
                    {/* Checkbox */}
                    <div className="flex-shrink-0">
                      {isSelected ? (
                        <CheckSquare className="h-5 w-5 text-primary" />
                      ) : (
                        <Square className="h-5 w-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                      )}
                    </div>

                    {/* Video Info */}
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-foreground truncate pr-2">
                        {video.title}
                      </h4>
                      <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDuration(video.duration)}
                        </div>
                        <div className="flex items-center gap-1">
                          <Video className="h-3 w-3" />
                          {video.video_id}
                        </div>
                        {video.uploader && (
                          <div className="flex items-center gap-1 truncate">
                            <Users className="h-3 w-3" />
                            <span className="truncate">{video.uploader}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="flex-shrink-0">
                      {(video as any).status && (
                        <Badge 
                          variant={
                            (video as any).status === 'completed' ? 'default' :
                            (video as any).status === 'failed' ? 'destructive' :
                            (video as any).status === 'processing' || (video as any).status === 'downloading' || (video as any).status === 'transcribing' ? 'secondary' :
                            'outline'
                          }
                          className={
                            (video as any).status === 'completed' ? 'bg-green-500 text-white border-green-500' :
                            (video as any).status === 'processing' || (video as any).status === 'downloading' || (video as any).status === 'transcribing' ? 'bg-blue-500 text-white border-blue-500' :
                            ''
                          }
                        >
                          {(video as any).status === 'pending' ? 'Pending' :
                           (video as any).status === 'downloading' ? 'Downloading' :
                           (video as any).status === 'transcribing' ? 'Transcribing' :
                           (video as any).status === 'processing' ? 'Processing' :
                           (video as any).status === 'completed' ? 'Completed' :
                           (video as any).status === 'failed' ? 'Failed' :
                           'Unknown'}
                        </Badge>
                      )}
                    </div>

                    {/* External Link */}
                    <div className="flex-shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                        disabled={disabled}
                      >
                        <a
                          href={video.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-muted-foreground hover:text-foreground"
                        >
                          <Eye className="h-4 w-4" />
                        </a>
                      </Button>
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          )}
        </div>

        {/* Summary */}
        {selectionStats.count > 0 && (
          <div className="bg-gradient-to-r from-primary/5 to-primary/10 border border-primary/20 rounded-lg p-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="text-sm">
                <span className="font-medium text-foreground">
                  {selectionStats.count} videos selected
                </span>
                <span className="text-muted-foreground ml-2">
                  • Total duration: ~{selectionStats.estimatedHours.toFixed(1)} hours
                </span>
              </div>
              
              {analysis.tier_limits && selectionStats.count > analysis.tier_limits.max_videos_per_job && (
                <Badge variant="destructive" className="text-xs">
                  Exceeds tier limit ({analysis.tier_limits.max_videos_per_job})
                </Badge>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

export type { VideoSelectorProps }