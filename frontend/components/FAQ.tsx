'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

interface FAQItem {
  question: string
  answer: string
}

const faqItems: FAQItem[] = [
  {
    question: "How does ytFetch work?",
    answer: "ytFetch uses advanced AI to transcribe YouTube videos quickly and accurately. Simply paste a YouTube URL, choose your format, and get your transcript in seconds. Each transcription uses 1 token."
  },
  {
    question: "What's included in the free tier?",
    answer: "Free users get 5 transcriptions per day without signing in. Sign up for a free account to purchase tokens and transcribe unlimited videos."
  },
  {
    question: "How does the token system work?",
    answer: "Tokens are credits you purchase to transcribe videos. 1 token = 1 video transcription, regardless of video length. Buy token packages starting at $2.99 for 50 tokens. Tokens never expire!"
  },
  {
    question: "What formats are supported?",
    answer: "We support TXT (plain text), SRT (subtitles), VTT (web captions), and JSON (structured data) formats. All formats are included with every transcription."
  },
  {
    question: "Do tokens expire?",
    answer: "No! Tokens never expire. Buy them once and use them whenever you need. Your token balance is permanently saved to your account."
  },
  {
    question: "How do I use bulk processing?",
    answer: "Click the 'Bulk Process' button, then enter a YouTube playlist or channel URL. Each video in the bulk job uses 1 token. Process entire playlists with a single click!"
  },
  {
    question: "How accurate are the transcriptions?",
    answer: "We use Groq's state-of-the-art AI models for transcription, achieving over 95% accuracy for clear audio. The 'Unofficial Transcript' option uses YouTube's own captions when available."
  },
  {
    question: "Can I get a refund?",
    answer: "Yes! We offer a 30-day money-back guarantee on token purchases. If you're not satisfied, contact support for a full refund on unused tokens."
  }
]

export function FAQ() {
  const [openItems, setOpenItems] = useState<number[]>([])

  const toggleItem = (index: number) => {
    setOpenItems(prev => 
      prev.includes(index) 
        ? prev.filter(i => i !== index)
        : [...prev, index]
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <Badge className="mb-4 bg-orange-500/10 text-orange-500 border-orange-500/20">
          Got Questions?
        </Badge>
        <h2 className="text-4xl md:text-5xl font-bold mb-4">Frequently Asked Questions</h2>
        <p className="text-xl text-zinc-400 max-w-2xl mx-auto">
          Everything you need to know about ytFetch's transcription service
        </p>
      </motion.div>

      <div className="space-y-4">
        {faqItems.map((item, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="group bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden hover:shadow-lg transition-all duration-300 hover:border-orange-500/20"
          >
            <button
              onClick={() => toggleItem(index)}
              className="w-full px-6 py-5 text-left flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
            >
              <span className="font-medium text-zinc-100 text-lg pr-4">{item.question}</span>
              <motion.div
                animate={{ rotate: openItems.includes(index) ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="w-5 h-5 text-zinc-500 group-hover:text-orange-500 transition-colors" />
              </motion.div>
            </button>
            
            <AnimatePresence>
              {openItems.includes(index) && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="px-6 pb-4 text-zinc-400">
                    {item.answer}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>

      <div className="mt-8 text-center text-sm text-zinc-500">
        <p>
          Have more questions? {' '}
          <a href="mailto:support@ytfetch.com" className="text-orange-500 hover:text-orange-400 hover:underline transition-colors">
            Contact support
          </a>
        </p>
      </div>
    </div>
  )
}