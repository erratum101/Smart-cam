import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { Hero } from "@/components/Hero";
import { ProductDemo } from "@/components/ProductDemo";
import { Features } from "@/components/Features";
import { Comparison } from "@/components/Comparison";
import { Pricing } from "@/components/Pricing";
import { Footer } from "@/components/Footer";

export default function Home() {
  return (
    <>
      <Background />
      <main className="relative">
        <Navbar />
        <Hero />
        <ProductDemo />
        <Features />
        <Comparison />
        <Pricing />
        <Footer />
      </main>
    </>
  );
}
